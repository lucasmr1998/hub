"""Agregações de analytics para o dashboard /analytics/.

Tudo recebe um intervalo (inicio, fim) e devolve dicts prontos pra
serializar em JSON. Sem efeitos colaterais — só leitura.
"""
from __future__ import annotations

from datetime import datetime, timedelta, date

from django.db.models import Count, Avg, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone


# Vendedores "automáticos" são identificados pelo PREFIXO do nome no Hubsoft.
# Ex.: "Venda-Automática-Matrix", "Venda-Automática".
PREFIXO_VENDEDOR_AUTOMATICO = 'Venda-Automática'

# Planos conhecidos (id_plano_rp → label)
PLANOS_LABEL = {
    1647: 'Plano 300MB',
    1649: 'Plano 620MB',
    1648: 'Plano 1GB Turbo',
    1650: 'Plano 2GB',
    2088: '1 Giga + Ponto Adicional',
}


def _parse_intervalo(inicio_str: str | None, fim_str: str | None):
    """Converte strings YYYY-MM-DD em datetimes aware. Default: últimos 30 dias."""
    hoje = timezone.localdate()
    if fim_str:
        try:
            fim_d = datetime.strptime(fim_str, '%Y-%m-%d').date()
        except ValueError:
            fim_d = hoje
    else:
        fim_d = hoje
    if inicio_str:
        try:
            ini_d = datetime.strptime(inicio_str, '%Y-%m-%d').date()
        except ValueError:
            ini_d = fim_d - timedelta(days=30)
    else:
        ini_d = fim_d - timedelta(days=30)

    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(ini_d, datetime.min.time()), tz)
    fim = timezone.make_aware(datetime.combine(fim_d, datetime.max.time()), tz)
    return inicio, fim, ini_d, fim_d


# ────────────────────────────────────────────────────────────────────
# 1. FUNIL DE CONVERSÃO
# ────────────────────────────────────────────────────────────────────

def funil_conversao(inicio, fim) -> dict:
    from vendas_web.models import LeadProspecto
    from integracoes.models import ClienteHubsoft

    base = LeadProspecto.objects.filter(data_cadastro__range=(inicio, fim))
    total_leads = base.count()

    # Cada etapa é um subconjunto progressivo
    com_cpf = base.exclude(Q(cpf_cnpj__isnull=True) | Q(cpf_cnpj='')).count()
    confirmou_dados = base.filter(dados_confirmados=True).count()
    docs_validados = base.filter(documentacao_validada=True).count()
    instalacao_agendada = base.filter(
        Q(data_instalacao__isnull=False) | Q(status_api='instalacao_agendada')
    ).count()

    # Quantos VIRARAM cliente (venda real): lead com cadastro criado no HubSoft
    # (id_hubsoft). O vínculo ClienteHubsoft.lead sozinho inclui clientes JÁ
    # EXISTENTES apenas reconhecidos pelo CPF — não é venda nova.
    virou_cliente = base.exclude(
        Q(id_hubsoft__isnull=True) | Q(id_hubsoft='')).count()

    etapas = [
        {'etapa': 'Leads recebidos',      'valor': total_leads},
        {'etapa': 'Informou CPF',         'valor': com_cpf},
        {'etapa': 'Confirmou dados',      'valor': confirmou_dados},
        {'etapa': 'Documentos validados', 'valor': docs_validados},
        {'etapa': 'Instalação agendada',  'valor': instalacao_agendada},
        {'etapa': 'Virou cliente Hubsoft','valor': virou_cliente},
    ]
    # Taxa relativa ao topo + relativa à etapa anterior
    for i, e in enumerate(etapas):
        e['pct_topo'] = round(e['valor'] / total_leads * 100, 1) if total_leads else 0.0
        if i == 0:
            e['pct_anterior'] = 100.0
        else:
            ant = etapas[i - 1]['valor']
            e['pct_anterior'] = round(e['valor'] / ant * 100, 1) if ant else 0.0

    return {
        'etapas': etapas,
        'total_leads': total_leads,
        'taxa_conversao_final': round(virou_cliente / total_leads * 100, 1) if total_leads else 0.0,
    }


# ────────────────────────────────────────────────────────────────────
# 2. ANÁLISE DE VENDEDOR (automático vs humano / reatribuição)
# ────────────────────────────────────────────────────────────────────

def analise_vendedor(inicio, fim) -> dict:
    """Compara vendas que nasceram automáticas e foram reatribuídas a humano.

    Considera serviços de clientes Hubsoft vinculados a leads gerados pela
    nossa automação (lead com id_vendedor_rp=1618 OU origem whatsapp).
    """
    from integracoes.models import ServicoClienteHubsoft

    # Serviços vinculados a clientes que têm lead nosso (FK preenchida)
    qs = ServicoClienteHubsoft.objects.filter(cliente__lead__isnull=False)

    # Filtra por data de venda do lead (data_cadastro) no período
    qs = qs.filter(cliente__lead__data_cadastro__range=(inicio, fim))

    total = qs.count()

    auto = qs.filter(vendedor_nome__startswith=PREFIXO_VENDEDOR_AUTOMATICO).count()
    reatribuidas = total - auto

    # Ranking de vendedores que receberam vendas reatribuídas
    ranking = list(
        qs.exclude(vendedor_nome__startswith=PREFIXO_VENDEDOR_AUTOMATICO)
          .exclude(vendedor_nome='')
          .values('vendedor_nome', 'id_vendedor')
          .annotate(n=Count('id'))
          .order_by('-n')[:15]
    )

    return {
        'total_vendas_automacao': total,
        'ainda_automatica': auto,
        'reatribuidas_humano': reatribuidas,
        'pct_reatribuidas': round(reatribuidas / total * 100, 1) if total else 0.0,
        'pct_automatica': round(auto / total * 100, 1) if total else 0.0,
        'ranking_vendedores': ranking,
    }


# ────────────────────────────────────────────────────────────────────
# 3. PERFORMANCE DA IA (LogInteracaoIA)
# ────────────────────────────────────────────────────────────────────

def performance_ia(inicio, fim) -> dict:
    from ia_validador.models import LogInteracaoIA

    qs = LogInteracaoIA.objects.filter(timestamp__range=(inicio, fim))
    total = qs.count()

    por_endpoint = {
        r['endpoint']: r['n']
        for r in qs.values('endpoint').annotate(n=Count('id'))
    }

    # Validação de respostas
    validacoes = qs.filter(endpoint='validar')
    val_ok = validacoes.filter(valido=True).count()
    val_fail = validacoes.filter(valido=False).count()

    # Validação de imagem
    imagens = qs.filter(endpoint='validar-imagem')
    img_total = imagens.count()
    # aprovado vem dentro de payload_out — contamos por motivo no fallback
    img_aprovadas = imagens.filter(payload_out__aprovado=True).count()
    img_rejeitadas = img_total - img_aprovadas

    transbordos = qs.filter(transbordou=True).count()
    duracao_media = qs.filter(duracao_ms__isnull=False).aggregate(
        m=Avg('duracao_ms'))['m'] or 0

    # Top perguntas que mais falham (valido=False)
    top_falhas = list(
        validacoes.filter(valido=False).exclude(question_id='')
        .values('question_id').annotate(n=Count('id')).order_by('-n')[:10]
    )

    # Volume por dia
    por_dia = list(
        qs.annotate(d=TruncDate('timestamp')).values('d')
        .annotate(n=Count('id')).order_by('d')
    )

    return {
        'total_interacoes': total,
        'por_endpoint': por_endpoint,
        'validacoes_ok': val_ok,
        'validacoes_falha': val_fail,
        'taxa_aprovacao_validacao': round(val_ok / (val_ok + val_fail) * 100, 1) if (val_ok + val_fail) else 0.0,
        'imagens_total': img_total,
        'imagens_aprovadas': img_aprovadas,
        'imagens_rejeitadas': img_rejeitadas,
        'taxa_aprovacao_imagem': round(img_aprovadas / img_total * 100, 1) if img_total else 0.0,
        'transbordos': transbordos,
        'duracao_media_ms': round(duracao_media),
        'top_falhas': top_falhas,
        'volume_por_dia': [{'data': r['d'].isoformat() if r['d'] else '', 'n': r['n']} for r in por_dia],
    }


# ────────────────────────────────────────────────────────────────────
# 4. VENDAS E INSTALAÇÕES NO TEMPO
# ────────────────────────────────────────────────────────────────────

def vendas_instalacoes(inicio, fim) -> dict:
    from vendas_web.models import LeadProspecto
    from integracoes.models import AgendamentoInstalacaoIA

    base = LeadProspecto.objects.filter(data_cadastro__range=(inicio, fim))

    # Leads por dia (proxy de "vendas iniciadas")
    leads_por_dia = list(
        base.annotate(d=TruncDate('data_cadastro')).values('d')
        .annotate(n=Count('id')).order_by('d')
    )

    # Distribuição por plano
    por_plano_raw = (
        base.exclude(id_plano_rp__isnull=True)
        .values('id_plano_rp').annotate(n=Count('id')).order_by('-n')
    )
    por_plano = [
        {'plano': PLANOS_LABEL.get(r['id_plano_rp'], f'Plano {r["id_plano_rp"]}'), 'n': r['n']}
        for r in por_plano_raw
    ]

    # Distribuição por turno
    por_turno_raw = (
        base.exclude(turno_instalacao='').values('turno_instalacao')
        .annotate(n=Count('id')).order_by('-n')
    )
    turno_label = {'manha': 'Manhã', 'tarde': 'Tarde'}
    por_turno = [
        {'turno': turno_label.get(r['turno_instalacao'], r['turno_instalacao']), 'n': r['n']}
        for r in por_turno_raw
    ]

    # Agendamentos de instalação (IA)
    ags = AgendamentoInstalacaoIA.objects.filter(data_criacao__range=(inicio, fim))
    ag_total = ags.count()
    ag_por_status = {
        r['status']: r['n'] for r in ags.values('status').annotate(n=Count('id'))
    }

    return {
        'leads_por_dia': [{'data': r['d'].isoformat() if r['d'] else '', 'n': r['n']} for r in leads_por_dia],
        'por_plano': por_plano,
        'por_turno': por_turno,
        'agendamentos_total': ag_total,
        'agendamentos_por_status': ag_por_status,
    }


# ────────────────────────────────────────────────────────────────────
# 5. INDICAÇÕES (funil manual operado por pessoas)
# ────────────────────────────────────────────────────────────────────

def indicacoes(inicio, fim) -> dict:
    from vendas_web.models import LeadProspecto
    from crm.models import OportunidadeVenda

    base = LeadProspecto.objects.filter(
        canal_entrada='indicacao', data_cadastro__range=(inicio, fim))
    total = base.count()
    convertidos = base.exclude(Q(id_hubsoft__isnull=True) | Q(id_hubsoft='')).count()

    # Top indicadores (código de quem indicou)
    top_indicadores = list(
        base.exclude(Q(id_indicador__isnull=True) | Q(id_indicador=''))
        .values('id_indicador').annotate(n=Count('id')).order_by('-n')[:10]
    )

    # Distribuição das oportunidades de indicação por estágio (fotografia atual)
    por_estagio = list(
        OportunidadeVenda.objects.filter(tipo='indicacao', ativo=True)
        .values(nome=F('estagio__nome'), ordem=F('estagio__ordem'))
        .annotate(n=Count('id')).order_by('ordem')
    )

    # Leads de indicação por dia
    por_dia = list(
        base.annotate(d=TruncDate('data_cadastro')).values('d')
        .annotate(n=Count('id')).order_by('d')
    )

    return {
        'total': total,
        'convertidos': convertidos,
        'taxa_conversao': round(convertidos / total * 100, 1) if total else 0.0,
        'top_indicadores': top_indicadores,
        'por_estagio': [{'estagio': r['nome'], 'n': r['n']} for r in por_estagio],
        'por_dia': [{'data': r['d'].isoformat() if r['d'] else '', 'n': r['n']} for r in por_dia],
    }


# ────────────────────────────────────────────────────────────────────
# 6. AUTOMAÇÃO HUBSOFT (execuções por API interna/webdriver)
# ────────────────────────────────────────────────────────────────────

def automacao_hubsoft(inicio, fim) -> dict:
    from posvenda_hubsoft.models import ExecucaoHubsoft

    qs = ExecucaoHubsoft.objects.filter(criado_em__range=(inicio, fim))
    total = qs.count()
    reais = qs.filter(dry_run=False)

    por_status = {r['status']: r['n'] for r in qs.values('status').annotate(n=Count('id'))}
    por_processo = list(
        qs.values('processo').annotate(
            n=Count('id'),
            sucesso=Count('id', filter=Q(status='sucesso')),
            falha=Count('id', filter=Q(status='falha')),
        ).order_by('-n')
    )
    sucesso_real = reais.filter(status='sucesso').count()
    falha_real = reais.filter(status='falha').count()
    fallbacks = qs.filter(tentativa_fallback=True).count()
    duracao_media = qs.filter(status='sucesso', duracao_ms__isnull=False).aggregate(
        m=Avg('duracao_ms'))['m'] or 0

    ultimas_falhas = list(
        qs.filter(status='falha').order_by('-criado_em')
        .values('processo', 'executor', 'etapa', 'erro', 'criado_em')[:8]
    )
    for f in ultimas_falhas:
        f['criado_em'] = f['criado_em'].isoformat() if f['criado_em'] else ''
        f['erro'] = (f['erro'] or '')[:140]

    return {
        'total_execucoes': total,
        'por_status': por_status,
        'por_processo': por_processo,
        'taxa_sucesso': round(sucesso_real / (sucesso_real + falha_real) * 100, 1)
                        if (sucesso_real + falha_real) else 0.0,
        'fallbacks_webdriver': fallbacks,
        'duracao_media_ms': round(duracao_media),
        'ultimas_falhas': ultimas_falhas,
    }


# ────────────────────────────────────────────────────────────────────
# 7. OPERAÇÃO CRM (tempo por estágio, aging, carga)
# ────────────────────────────────────────────────────────────────────

def operacao_crm(inicio, fim) -> dict:
    from crm.models import OportunidadeVenda, HistoricoPipelineEstagio

    # Tempo médio (horas) gasto em cada estágio — do histórico de transições
    tempos = list(
        HistoricoPipelineEstagio.objects.filter(
            data_transicao__range=(inicio, fim),
            tempo_no_estagio_horas__isnull=False,
            estagio_anterior__isnull=False,
        )
        .values(nome=F('estagio_anterior__nome'))
        .annotate(media_h=Avg('tempo_no_estagio_horas'), n=Count('id'))
        .order_by('-media_h')[:12]
    )
    for t in tempos:
        t['media_h'] = round(float(t['media_h'] or 0), 1)

    # Oportunidades PARADAS: ativas, fora de estágio final, sem mover há 7+ dias
    agora = timezone.now()
    limite = agora - timedelta(days=7)
    ativas = OportunidadeVenda.objects.filter(
        ativo=True, estagio__is_final_ganho=False, estagio__is_final_perdido=False)
    paradas_qs = ativas.filter(data_entrada_estagio__lt=limite)
    paradas = list(
        paradas_qs.values(pipeline=F('estagio__pipeline_tipo'))
        .annotate(n=Count('id')).order_by('-n')
    )

    # Carga por responsável (oportunidades ativas)
    carga = list(
        ativas.exclude(responsavel__isnull=True)
        .values(nome=F('responsavel__username'))
        .annotate(n=Count('id')).order_by('-n')[:10]
    )
    sem_responsavel = ativas.filter(responsavel__isnull=True).count()

    return {
        'tempo_medio_por_estagio': tempos,
        'paradas_7d_total': paradas_qs.count(),
        'paradas_por_pipeline': paradas,
        'carga_por_responsavel': carga,
        'sem_responsavel': sem_responsavel,
        'ativas_total': ativas.count(),
    }


# ────────────────────────────────────────────────────────────────────
# 8. ROBÔ — ATRITO E TRANSBORDO (complementa performance_ia)
# ────────────────────────────────────────────────────────────────────

def robo_atrito(inicio, fim) -> dict:
    from ia_validador.models import LogInteracaoIA

    validacoes = LogInteracaoIA.objects.filter(
        timestamp__range=(inicio, fim), endpoint='validar').exclude(question_id='')

    # Atrito por pergunta: % de respostas inválidas (mín. 5 tentativas)
    atrito = list(
        validacoes.values('question_id').annotate(
            total=Count('id'),
            invalidas=Count('id', filter=Q(valido=False)),
        ).filter(total__gte=5).order_by('-invalidas')
    )
    for a in atrito:
        a['pct_invalidas'] = round(a['invalidas'] / a['total'] * 100, 1) if a['total'] else 0.0
    atrito.sort(key=lambda a: -a['pct_invalidas'])

    # Recontatos (tempo de espera) — reengajamento
    recontatos = LogInteracaoIA.objects.filter(
        timestamp__range=(inicio, fim), endpoint='recontato')

    return {
        'atrito_por_pergunta': atrito[:10],
        'recontatos_disparados': recontatos.count(),
    }


# ────────────────────────────────────────────────────────────────────
# CARDS DE RESUMO (KPIs do topo)
# ────────────────────────────────────────────────────────────────────

def kpis_resumo(inicio, fim) -> dict:
    from vendas_web.models import LeadProspecto
    from integracoes.models import ClienteHubsoft, AgendamentoInstalacaoIA

    base = LeadProspecto.objects.filter(data_cadastro__range=(inicio, fim))
    total_leads = base.count()
    # Venda real = cadastro criado no HubSoft (id_hubsoft) — não conta cliente
    # já existente apenas reconhecido pelo CPF (mesma régua do funil/indicações).
    clientes = base.exclude(Q(id_hubsoft__isnull=True) | Q(id_hubsoft='')).count()
    agendamentos = AgendamentoInstalacaoIA.objects.filter(
        data_criacao__range=(inicio, fim), status='agendado'
    ).count()
    docs_validados = base.filter(documentacao_validada=True).count()

    return {
        'total_leads': total_leads,
        'clientes_convertidos': clientes,
        'taxa_conversao': round(clientes / total_leads * 100, 1) if total_leads else 0.0,
        'instalacoes_agendadas': agendamentos,
        'docs_validados': docs_validados,
    }


def montar_payload(inicio_str: str | None, fim_str: str | None) -> dict:
    """Monta o payload completo do dashboard pra um intervalo."""
    inicio, fim, ini_d, fim_d = _parse_intervalo(inicio_str, fim_str)
    return {
        'periodo': {'inicio': ini_d.isoformat(), 'fim': fim_d.isoformat()},
        'kpis': kpis_resumo(inicio, fim),
        'funil': funil_conversao(inicio, fim),
        'vendedor': analise_vendedor(inicio, fim),
        'ia': performance_ia(inicio, fim),
        'vendas': vendas_instalacoes(inicio, fim),
        'indicacoes': indicacoes(inicio, fim),
        'automacao': automacao_hubsoft(inicio, fim),
        'operacao': operacao_crm(inicio, fim),
        'robo': robo_atrito(inicio, fim),
    }
