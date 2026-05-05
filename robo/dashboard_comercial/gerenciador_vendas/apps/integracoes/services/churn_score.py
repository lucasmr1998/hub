"""
Calculadora rule-based de churn score para ClienteHubsoft.

Score 0-100 baseado em sinais que indicam risco de cancelamento.
Threshold sugerido:
  - 0-39: saudável
  - 40-59: atenção
  - 60-100: alto risco

Sinais ponderados:
  - Inadimplência atual: +25
  - 2+ tickets de suporte abertos no mês: +30
  - Cliente novo (< 6 meses): +10  (pode também indicar instabilidade)
  - Cliente longo (> 36 meses): +5  (curva da banheira)
  - Sem atividade no app/portal nos últimos 30d: +20
  - NPS detrator nos últimos 90d: +25

Sinais SEM dados disponíveis hoje retornam 0 (defensivo). Quando o módulo
correspondente estiver implementado (NPS, app metrics), o sinal liga.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def calcular(cliente):
    """
    Calcula churn score do cliente. Retorna (score, sinais_dict).

    Args:
        cliente: instância de ClienteHubsoft (ou similar com .data_cadastro_hubsoft, etc)

    Returns:
        tuple (int score 0-100, dict sinais aplicados com pesos)
    """
    sinais = {}
    score = 0

    agora = timezone.now()

    # --- Idade do cliente -----------------------------------------------------
    if cliente.data_cadastro_hubsoft:
        meses = (agora - cliente.data_cadastro_hubsoft).days / 30
        if meses < 6:
            sinais['cliente_novo_menos_6m'] = 10
            score += 10
        elif meses > 36:
            sinais['cliente_longo_mais_36m'] = 5
            score += 5

    # --- Inadimplência --------------------------------------------------------
    # Heurística: alerta=True ou mensagens contendo 'cobrança', 'atraso', 'pendência'
    alerta_msgs = ' '.join(cliente.alerta_mensagens or []).lower() if cliente.alerta_mensagens else ''
    if cliente.alerta and any(p in alerta_msgs for p in ('cobranca', 'cobrança', 'atraso', 'pendencia', 'pendência', 'inadimpl')):
        sinais['inadimplente'] = 25
        score += 25

    # --- Tickets de suporte abertos ------------------------------------------
    try:
        from apps.suporte.models import Ticket
        janela_30d = agora - timedelta(days=30)
        # Tickets do cliente que ainda estão abertos
        if cliente.lead:
            tickets_abertos = Ticket.objects.filter(
                lead=cliente.lead,
                criado_em__gte=janela_30d,
            ).exclude(status__in=['fechado', 'resolvido']).count()
            if tickets_abertos >= 2:
                sinais['multiplos_tickets_abertos'] = 30
                score += 30
            elif tickets_abertos >= 1:
                sinais['ticket_aberto'] = 10
                score += 10
    except Exception as exc:
        logger.debug('Não foi possível avaliar tickets pra cliente %s: %s', cliente.id, exc)

    # --- Conversas recentes (atividade) --------------------------------------
    try:
        from apps.inbox.models import Conversa
        janela_30d = agora - timedelta(days=30)
        conversas_recentes = Conversa.objects.filter(
            tenant=cliente.tenant,
            contato_telefone__icontains=(cliente.telefone_primario or '')[-9:] if cliente.telefone_primario else '',
            criado_em__gte=janela_30d,
        ).count() if cliente.telefone_primario else 0
        if conversas_recentes == 0:
            sinais['sem_atividade_30d'] = 20
            score += 20
    except Exception as exc:
        logger.debug('Não foi possível avaliar atividade pra cliente %s: %s', cliente.id, exc)

    # --- NPS detrator (placeholder até módulo NPS existir) -------------------
    # TODO: quando apps/cs/nps/models.py tiver Avaliacao, ligar este sinal
    # try:
    #     from apps.cs.nps.models import AvaliacaoNPS
    #     ultima_aval = AvaliacaoNPS.objects.filter(cliente=cliente).order_by('-criado_em').first()
    #     if ultima_aval and ultima_aval.nota <= 6:
    #         sinais['nps_detrator'] = 25
    #         score += 25
    # except Exception:
    #     pass

    # Cap em 100
    score = min(100, score)
    return score, sinais


def classificar(score):
    """Retorna categoria pelo score: 'saudavel', 'atencao', 'alto_risco'."""
    if score is None:
        return 'sem_dados'
    if score < 40:
        return 'saudavel'
    if score < 60:
        return 'atencao'
    return 'alto_risco'
