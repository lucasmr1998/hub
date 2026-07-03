"""Hub de eventos da engine de automação — ponto de entrada neutro.

Relocado de `apps.marketing.automacoes.engine.disparar_evento`: os signals do sistema
(inbox, crm, leads, oportunidade, indicação) chamam ESTE hub, que enfileira os fluxos
que escutam o evento via `gatilhos.on_evento`. NÃO depende do motor antigo de marketing
(aposentado). Nunca quebra o emissor — toda falha é logada e ignorada. O kill-switch
`settings.AUTOMACAO_WIRING_ATIVO` e o guard de re-entrância vivem no `on_evento`.
"""
import logging

logger = logging.getLogger(__name__)


def disparar_evento(evento, contexto=None, tenant=None):
    """Enfileira os fluxos da engine nova que escutam `evento`. Blindado.

    `tenant` opcional cai pro tenant atual (middleware) — compat com os call sites
    que não passam tenant explícito.
    """
    from .gatilhos import on_evento
    if tenant is None:
        from apps.sistema.middleware import get_current_tenant
        tenant = get_current_tenant()
    if not evento or tenant is None:
        return
    # Shadow (migração do funil): avalia log-only os fluxos migrados que escutam o
    # evento, em paralelo. Gated por AUTOMACAO_SHADOW_ATIVO, independente do wiring.
    try:
        from .shadow import avaliar_evento_shadow
        avaliar_evento_shadow(evento, contexto or {}, tenant)
    except Exception:  # noqa: BLE001
        logger.exception('automacao.hub: shadow falhou (evento=%s)', evento)
    try:
        on_evento(evento, contexto or {}, tenant)
    except Exception:  # noqa: BLE001
        logger.exception('automacao.hub: disparar_evento falhou (evento=%s)', evento)
