"""
Servico que monta o resumo diario comercial pra um tenant.

Uso:
    from apps.comercial.crm.services.resumo_diario import montar_resumo, formatar_whatsapp
    dados = montar_resumo(tenant, dia)  # dia default = ontem BRT
    texto = formatar_whatsapp(dados, nome_destinatario='Gabi')

Design:
- Todas as queries filtradas por tenant.
- Timezone BRT usado consistentemente pra "dia".
- "Hoje" = pipeline snapshot (nao depende de data).
- "Dia fechado" = agregado do dia passado como argumento (default ontem).
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from apps.comercial.crm.models import (
    HistoricoPipelineEstagio,
    OportunidadeVenda,
)


def _hoje_brt():
    return timezone.localtime().date()


def montar_resumo(tenant, dia=None):
    """
    Monta o resumo diario pro tenant.

    Args:
        tenant: Tenant
        dia: date do dia a agregar (default: ontem BRT).
             Se voce chama isso amanha 8h, dia sera hoje-1 = hoje 02/07.

    Returns:
        dict com metricas do dia + snapshot do pipeline atual.
    """
    if dia is None:
        dia = _hoje_brt() - timedelta(days=1)
    dia_anterior = dia - timedelta(days=1)

    # ── DIA FECHADO ──
    # Novas oportunidades (nao leads): alinha com o card "Oportunidades" do
    # painel. Na Nuvyon o webhook cria a op junto do lead, entao e 1:1.
    ops_dia = OportunidadeVenda.objects.filter(
        tenant=tenant, data_criacao__date=dia,
    ).count()
    ops_dia_anterior = OportunidadeVenda.objects.filter(
        tenant=tenant, data_criacao__date=dia_anterior,
    ).count()

    # Vendas confirmadas no HubSoft (ClienteHubsoft criado)
    try:
        from apps.integracoes.models import ClienteHubsoft
        vendas_hubsoft = ClienteHubsoft.objects.filter(
            tenant=tenant, data_cadastro_hubsoft__date=dia,
        ).count()
        vendas_hubsoft_anterior = ClienteHubsoft.objects.filter(
            tenant=tenant, data_cadastro_hubsoft__date=dia_anterior,
        ).count()
    except Exception:
        vendas_hubsoft = 0
        vendas_hubsoft_anterior = 0

    # Ops que caem em estagios finais (ganho/perdido) no dia
    perdidas_dia = OportunidadeVenda.objects.filter(
        tenant=tenant,
        data_fechamento_real__date=dia,
        estagio__is_final_perdido=True,
    ).count()
    ganhas_dia = OportunidadeVenda.objects.filter(
        tenant=tenant,
        data_fechamento_real__date=dia,
        estagio__is_final_ganho=True,
    ).count()
    ganhas_dia_anterior = OportunidadeVenda.objects.filter(
        tenant=tenant,
        data_fechamento_real__date=dia_anterior,
        estagio__is_final_ganho=True,
    ).count()

    # Movimentacoes de estagio no dia
    mov_qs = HistoricoPipelineEstagio.objects.filter(
        tenant=tenant, data_transicao__date=dia,
    ).select_related('estagio_anterior', 'estagio_novo')
    total_movs = mov_qs.count()

    # Top 5 fluxos mais fortes
    fluxo_agrupado = mov_qs.values(
        'estagio_anterior__nome', 'estagio_novo__nome',
    ).annotate(total=Count('id')).order_by('-total')[:5]
    fluxos_top = [
        {
            'de': f['estagio_anterior__nome'] or 'entrada',
            'para': f['estagio_novo__nome'] or '-',
            'total': f['total'],
        }
        for f in fluxo_agrupado
    ]

    # Contratos assinados no dia (movimentacao pra "Contrato Assinado")
    contratos_assinados = mov_qs.filter(
        estagio_novo__nome__icontains='Contrato Assinado',
    ).count()

    # ── PIPELINE ATIVO (snapshot agora) ──
    ativos = OportunidadeVenda.objects.filter(
        tenant=tenant, ativo=True,
        estagio__is_final_ganho=False,
        estagio__is_final_perdido=False,
    )
    total_pipeline = ativos.count()

    por_estagio = list(ativos.values(
        'estagio__nome', 'estagio__ordem',
    ).annotate(total=Count('id')).order_by('estagio__ordem'))
    por_estagio = [
        {'nome': e['estagio__nome'] or '-', 'total': e['total']}
        for e in por_estagio
    ]

    # Ranking exclui usuarios robo (QA/automatizados) definidos em settings
    robos = getattr(settings, 'USUARIOS_ROBO_RELATORIOS', [])
    ativos_ranking = ativos.exclude(responsavel__username__in=robos) if robos else ativos
    por_vendedora = list(ativos_ranking.values(
        'responsavel__first_name',
    ).annotate(total=Count('id')).order_by('-total'))
    por_vendedora = [
        {
            'nome': (v['responsavel__first_name'] or 'Sem responsavel').strip(),
            'total': v['total'],
        }
        for v in por_vendedora
    ]

    # ── ALERTAS ──
    limite_paradas = timezone.now() - timedelta(days=3)
    paradas = ativos.filter(data_atualizacao__lt=limite_paradas).count()
    sem_responsavel = ativos.filter(responsavel__isnull=True).count()

    return {
        'dia': dia,
        'dia_semana_pt': _dia_semana(dia),
        'ops_dia': ops_dia,
        'ops_dia_anterior': ops_dia_anterior,
        'vendas_hubsoft': vendas_hubsoft,
        'vendas_hubsoft_anterior': vendas_hubsoft_anterior,
        'contratos_assinados': contratos_assinados,
        'perdidas': perdidas_dia,
        'ganhas_crm': ganhas_dia,
        'ganhas_crm_anterior': ganhas_dia_anterior,
        'movimentacoes': total_movs,
        'fluxos_top': fluxos_top,
        'total_pipeline': total_pipeline,
        'por_estagio': por_estagio,
        'por_vendedora': por_vendedora,
        'paradas_mais_3_dias': paradas,
        'sem_responsavel': sem_responsavel,
    }


def montar_resumo_vendedoras(tenant, dia=None):
    """Resumo diario POR VENDEDORA (pedido da Gabi 10/07): pra cada uma,
    o movimento do dia (recebidas, fechadas, perdidas e quantas perdidas
    com motivo Sem retorno) + snapshot da carteira ativa e paradas 3d+.

    Retorna dict com `dia` e `vendedoras` (lista ordenada por fechadas,
    depois recebidas). Vendedora sem movimento no dia e sem carteira fica
    de fora. Usuarios robo (settings.USUARIOS_ROBO_RELATORIOS) excluidos.
    """
    if dia is None:
        dia = _hoje_brt() - timedelta(days=1)

    robos = getattr(settings, 'USUARIOS_ROBO_RELATORIOS', [])
    ops = OportunidadeVenda.objects.filter(
        tenant=tenant, responsavel__isnull=False,
    )
    if robos:
        ops = ops.exclude(responsavel__username__in=robos)

    limite_paradas = timezone.now() - timedelta(days=3)
    q_ativa = Q(estagio__is_final_ganho=False, estagio__is_final_perdido=False, ativo=True)
    agregado = ops.values('responsavel__first_name', 'responsavel__username').annotate(
        recebidas=Count('id', filter=Q(data_criacao__date=dia)),
        fechadas=Count('id', filter=Q(
            estagio__is_final_ganho=True, data_fechamento_real__date=dia)),
        perdidas=Count('id', filter=Q(
            estagio__is_final_perdido=True, data_fechamento_real__date=dia)),
        sem_retorno=Count('id', filter=Q(
            estagio__is_final_perdido=True, data_fechamento_real__date=dia,
            motivo_perda_ref__nome__icontains='sem retorno')),
        carteira=Count('id', filter=q_ativa),
        paradas=Count('id', filter=q_ativa & Q(data_atualizacao__lt=limite_paradas)),
    )

    vendedoras = []
    for v in agregado:
        if not any((v['recebidas'], v['fechadas'], v['perdidas'], v['carteira'])):
            continue
        nome = (v['responsavel__first_name'] or v['responsavel__username'] or '').strip()
        vendedoras.append({
            'nome': nome,
            'recebidas': v['recebidas'],
            'fechadas': v['fechadas'],
            'perdidas': v['perdidas'],
            'sem_retorno': v['sem_retorno'],
            'carteira': v['carteira'],
            'paradas': v['paradas'],
            'teve_movimento': bool(v['recebidas'] or v['fechadas'] or v['perdidas']),
        })
    vendedoras.sort(key=lambda v: (-v['fechadas'], -v['recebidas'], -v['carteira']))

    return {
        'dia': dia,
        'dia_semana_pt': _dia_semana(dia),
        'vendedoras': vendedoras,
    }


def formatar_whatsapp_vendedoras(dados, nome_destinatario='pessoal', nome_tenant='comercial'):
    """Formata o resumo por vendedora pra WhatsApp: bloco completo pra quem
    teve movimento no dia, linha compacta pras demais, alerta de paradas."""
    d = dados
    dia_fmt = d['dia'].strftime('%d/%m')
    linha_sep = '━' * 22
    linhas = []
    linhas.append(f"🧑‍💼 Bom dia, {nome_destinatario}! Vendedoras {nome_tenant} — {dia_fmt} ({d['dia_semana_pt']})")
    linhas.append('')
    linhas.append(linha_sep)
    linhas.append('📊 *MOVIMENTO DO DIA*')
    linhas.append(linha_sep)

    com_mov = [v for v in d['vendedoras'] if v['teve_movimento']]
    sem_mov = [v for v in d['vendedoras'] if not v['teve_movimento']]

    if not com_mov:
        linhas.append('')
        linhas.append('Nenhuma vendedora movimentou oportunidades no dia.')
    for v in com_mov:
        linhas.append('')
        linhas.append(f"*{v['nome'].upper()}*")
        perdeu = f"perdeu {v['perdidas']}"
        if v['sem_retorno']:
            perdeu += f" ({v['sem_retorno']} sem retorno)"
        linhas.append(f"   recebeu {v['recebidas']} · fechou *{v['fechadas']}* · {perdeu}")
        carteira = f"   carteira: {v['carteira']} ativas"
        if v['paradas']:
            carteira += f" ({v['paradas']} paradas 3d+)"
        linhas.append(carteira)

    if sem_mov:
        linhas.append('')
        linhas.append('*Sem movimento no dia:*')
        linhas.append('   ' + ' · '.join(
            f"{v['nome']} {v['carteira']}" + (f" ({v['paradas']}⚠)" if v['paradas'] else '')
            for v in sem_mov
        ))

    alertas = [v for v in d['vendedoras'] if v['paradas']]
    if alertas:
        linhas.append('')
        linhas.append(linha_sep)
        linhas.append('⚠️ *CARTEIRA PARADA HA 3+ DIAS*')
        linhas.append(linha_sep)
        linhas.append('')
        for v in sorted(alertas, key=lambda x: -x['paradas']):
            linhas.append(f"   • {v['nome']}: {v['paradas']} de {v['carteira']}")

    linhas.append('')
    linhas.append('Bom dia e boa venda! ☕')
    return '\n'.join(linhas)


_DIAS_SEMANA = [
    'segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo',
]


def _dia_semana(d):
    return _DIAS_SEMANA[d.weekday()]


def formatar_whatsapp(dados, nome_destinatario='pessoal', nome_tenant='comercial'):
    """
    Formata o resumo pra WhatsApp.

    Args:
        dados: retorno de montar_resumo()
        nome_destinatario: primeiro nome do destinatario (ex: 'Gabi')
        nome_tenant: nome amigavel do tenant (ex: 'Nuvyon')

    Returns:
        str com formatacao WhatsApp (*negrito*, quebras de linha).
    """
    d = dados
    dia_fmt = d['dia'].strftime('%d/%m')
    linha_sep = '━' * 22
    linhas = []
    linhas.append(f"🌅 Bom dia, {nome_destinatario}! Resumo {nome_tenant} — {dia_fmt} ({d['dia_semana_pt']})")
    linhas.append('')
    linhas.append(linha_sep)
    linhas.append('📊 *COMO ONTEM FECHOU*')
    linhas.append(linha_sep)
    linhas.append('')
    linhas.append(f"📥 Novas oportunidades: *{d['ops_dia']}* (dia anterior: {d['ops_dia_anterior']})")
    linhas.append(f"✅ Vendas fechadas (CRM): *{d['ganhas_crm']}* (dia anterior: {d['ganhas_crm_anterior']})")
    if d['contratos_assinados']:
        linhas.append(f"📝 Contratos assinados: {d['contratos_assinados']}")
    linhas.append(f"🚫 Perdidas: {d['perdidas']}")
    linhas.append(f"🔄 Movimentacoes de estagio: *{d['movimentacoes']}*")

    if d['fluxos_top']:
        linhas.append('')
        linhas.append('*Fluxo mais forte do dia:*')
        for f in d['fluxos_top']:
            linhas.append(f"   • {f['de']} → {f['para']}: {f['total']}")

    linhas.append('')
    linhas.append(linha_sep)
    linhas.append(f"📋 *PIPELINE AGORA — {d['total_pipeline']} ops*")
    linhas.append(linha_sep)
    linhas.append('')

    if d['por_estagio']:
        linhas.append('*Por estagio:*')
        for e in d['por_estagio']:
            linhas.append(f"   • {e['nome']}: {e['total']}")
        linhas.append('')

    # Ranking por vendedora saiu do resumo geral em 10/07: virou o resumo
    # dedicado `resumo_diario_vendedoras` (montar_resumo_vendedoras), com
    # mais dados por pessoa, a pedido da Gabi.

    if d['paradas_mais_3_dias'] or d['sem_responsavel']:
        linhas.append('')
        linhas.append(linha_sep)
        linhas.append('⚠️ *ATENCAO*')
        linhas.append(linha_sep)
        linhas.append('')
        if d['paradas_mais_3_dias']:
            linhas.append(f"   • {d['paradas_mais_3_dias']} oportunidades paradas ha mais de 3 dias")
        if d['sem_responsavel']:
            linhas.append(f"   • {d['sem_responsavel']} oportunidade(s) sem responsavel")
            linhas.append(f"     Ver e atribuir: {settings.SITE_URL}/crm/oportunidades/?responsavel=sem")

    linhas.append('')
    linhas.append('Bom dia e boa venda! ☕')
    return '\n'.join(linhas)
