"""
Calculadora rule-based de churn score para ClienteHubsoft.

Os pesos e quais sinais aplicar vêm de ConfiguracaoChurnScore (singleton
por tenant). Tenant pode customizar via /configuracoes/churn-score/.

Score 0-100. Classificação configurável por tenant via thresholds.
Defaults Hubtrix:
  - 0-39: saudável
  - 40-59: atenção
  - 60-100: alto risco

Sinais (todos toggláveis e ponderáveis por tenant):
  - Inadimplência ativa
  - 2+ tickets abertos no mês (qtd mínima configurável)
  - 1 ticket aberto
  - Sem atividade nos últimos N dias (N configurável)
  - Cliente novo (< N meses, configurável)
  - Cliente longo (> N meses, configurável)
  - NPS detrator (placeholder até módulo NPS existir)
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_config(tenant):
    """Carrega config do tenant, com fallback pra defaults."""
    from apps.integracoes.models import ConfiguracaoChurnScore
    return ConfiguracaoChurnScore.get_or_create_default(tenant)


def calcular(cliente):
    """
    Calcula churn score do cliente. Retorna (score, sinais_dict).

    Args:
        cliente: instância de ClienteHubsoft (ou similar com tenant)

    Returns:
        tuple (int score 0-100, dict sinais aplicados com pesos)
    """
    config = _get_config(cliente.tenant)
    sinais = {}
    score = 0

    agora = timezone.now()

    # --- Idade do cliente -----------------------------------------------------
    if cliente.data_cadastro_hubsoft:
        meses = (agora - cliente.data_cadastro_hubsoft).days / 30
        if config.cliente_novo_ativo and meses < config.cliente_novo_meses:
            sinais['cliente_novo'] = config.cliente_novo_peso
            score += config.cliente_novo_peso
        elif config.cliente_longo_ativo and meses > config.cliente_longo_meses:
            sinais['cliente_longo'] = config.cliente_longo_peso
            score += config.cliente_longo_peso

    # --- Inadimplência --------------------------------------------------------
    alerta_msgs = ' '.join(cliente.alerta_mensagens or []).lower() if cliente.alerta_mensagens else ''
    if (config.inadimplencia_ativo and cliente.alerta and
        any(p in alerta_msgs for p in ('cobranca', 'cobrança', 'atraso', 'pendencia', 'pendência', 'inadimpl'))):
        sinais['inadimplente'] = config.inadimplencia_peso
        score += config.inadimplencia_peso

    # --- Tickets de suporte abertos ------------------------------------------
    try:
        from apps.suporte.models import Ticket
        janela_30d = agora - timedelta(days=30)
        if cliente.lead:
            tickets_abertos = Ticket.objects.filter(
                lead=cliente.lead,
                criado_em__gte=janela_30d,
            ).exclude(status__in=['fechado', 'resolvido']).count()
            if config.multiplos_tickets_ativo and tickets_abertos >= config.multiplos_tickets_minimo:
                sinais['multiplos_tickets'] = config.multiplos_tickets_peso
                score += config.multiplos_tickets_peso
            elif config.ticket_aberto_ativo and tickets_abertos >= 1:
                sinais['ticket_aberto'] = config.ticket_aberto_peso
                score += config.ticket_aberto_peso
    except Exception as exc:
        logger.debug('Não foi possível avaliar tickets pra cliente %s: %s', cliente.id, exc)

    # --- Conversas recentes (atividade) --------------------------------------
    if config.sem_atividade_ativo:
        try:
            from apps.inbox.models import Conversa
            janela = agora - timedelta(days=config.sem_atividade_dias)
            conversas_recentes = 0
            if cliente.telefone_primario:
                conversas_recentes = Conversa.objects.filter(
                    tenant=cliente.tenant,
                    contato_telefone__icontains=cliente.telefone_primario[-9:],
                    criado_em__gte=janela,
                ).count()
            if conversas_recentes == 0:
                sinais['sem_atividade'] = config.sem_atividade_peso
                score += config.sem_atividade_peso
        except Exception as exc:
            logger.debug('Não foi possível avaliar atividade pra cliente %s: %s', cliente.id, exc)

    # --- NPS detrator --------------------------------------------------------
    if config.nps_detrator_ativo:
        try:
            from apps.cs.nps.models import AvaliacaoNPS  # noqa
            ultima = AvaliacaoNPS.objects.filter(
                tenant=cliente.tenant,
                cliente=cliente,
            ).order_by('-criado_em').first()
            if ultima and ultima.nota <= 6:
                sinais['nps_detrator'] = config.nps_detrator_peso
                score += config.nps_detrator_peso
        except Exception:
            pass  # módulo NPS pode não existir ainda

    score = min(100, score)
    return score, sinais


def classificar(score, tenant=None):
    """
    Retorna categoria pelo score: 'saudavel', 'atencao', 'alto_risco'.
    Se tenant fornecido, usa thresholds configurados; senão usa defaults.
    """
    if score is None:
        return 'sem_dados'

    if tenant is not None:
        config = _get_config(tenant)
        if score < config.threshold_atencao:
            return 'saudavel'
        if score < config.threshold_alto_risco:
            return 'atencao'
        return 'alto_risco'

    # Fallback hardcoded (compat com código antigo que não passa tenant)
    if score < 40:
        return 'saudavel'
    if score < 60:
        return 'atencao'
    return 'alto_risco'


def calcular_score_preview(tenant, sinais_simulados):
    """
    Calcula score sem cliente real, simulando quais sinais estariam ativos.
    Usado pelo preview da UI.

    Args:
        tenant: Tenant
        sinais_simulados: lista de strings ex: ['inadimplencia', 'multiplos_tickets']

    Returns:
        tuple (score, classe)
    """
    config = _get_config(tenant)
    score = 0

    pesos = {
        'inadimplencia': (config.inadimplencia_ativo, config.inadimplencia_peso),
        'multiplos_tickets': (config.multiplos_tickets_ativo, config.multiplos_tickets_peso),
        'ticket_aberto': (config.ticket_aberto_ativo, config.ticket_aberto_peso),
        'sem_atividade': (config.sem_atividade_ativo, config.sem_atividade_peso),
        'cliente_novo': (config.cliente_novo_ativo, config.cliente_novo_peso),
        'cliente_longo': (config.cliente_longo_ativo, config.cliente_longo_peso),
        'nps_detrator': (config.nps_detrator_ativo, config.nps_detrator_peso),
    }

    for sinal in sinais_simulados:
        if sinal in pesos:
            ativo, peso = pesos[sinal]
            if ativo:
                score += peso

    score = min(100, score)
    return score, classificar(score, tenant=tenant)
