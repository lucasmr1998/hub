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
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.comercial.crm.models import (
    HistoricoPipelineEstagio,
    OportunidadeVenda,
    PipelineEstagio,
)
from apps.comercial.leads.models import LeadProspecto


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
    leads_dia = LeadProspecto.objects.filter(
        tenant=tenant, data_cadastro__date=dia,
    ).count()
    leads_dia_anterior = LeadProspecto.objects.filter(
        tenant=tenant, data_cadastro__date=dia_anterior,
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

    por_vendedora = list(ativos.values(
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
        'leads_dia': leads_dia,
        'leads_dia_anterior': leads_dia_anterior,
        'vendas_hubsoft': vendas_hubsoft,
        'vendas_hubsoft_anterior': vendas_hubsoft_anterior,
        'contratos_assinados': contratos_assinados,
        'perdidas': perdidas_dia,
        'ganhas_crm': ganhas_dia,
        'movimentacoes': total_movs,
        'fluxos_top': fluxos_top,
        'total_pipeline': total_pipeline,
        'por_estagio': por_estagio,
        'por_vendedora': por_vendedora,
        'paradas_mais_3_dias': paradas,
        'sem_responsavel': sem_responsavel,
    }


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
    linhas.append(f"📥 Atendimentos: *{d['leads_dia']}* (dia anterior: {d['leads_dia_anterior']})")
    linhas.append(f"✅ Vendas fechadas HubSoft: *{d['vendas_hubsoft']}* (dia anterior: {d['vendas_hubsoft_anterior']})")
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

    if d['por_vendedora']:
        linhas.append('*Por vendedora:*')
        for v in d['por_vendedora']:
            linhas.append(f"   • {v['nome']}: {v['total']}")

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

    linhas.append('')
    linhas.append('Bom dia e boa venda! ☕')
    return '\n'.join(linhas)
