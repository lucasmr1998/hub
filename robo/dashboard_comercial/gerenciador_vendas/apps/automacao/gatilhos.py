"""
Camada de gatilho unificada — dispatch de evento do sistema p/ a engine.

`on_evento(evento, contexto, tenant)` é o ponto único: achado pelo hook blindado
no `disparar_evento` do motor de marketing (onde TODOS os eventos já passam),
encontra os fluxos que escutam aquele evento, avalia os filtros e **enfileira**
a execução (status `pendente`). Quem roda o fluxo é o cron (`rodar_novos`), fora
do thread do evento — o evento nunca espera. (Modelo deferido: não sobrecarrega.)

Segurança:
- Kill-switch `settings.AUTOMACAO_WIRING_ATIVO` (liga/desliga sem deploy).
- Tudo por tenant explícito (a engine roda fora de request).
- Tudo embrulhado: uma falha aqui NUNCA quebra o motor que disparou o evento.
- Guard de re-entrância (thread-local) contra cascata no mesmo request.
"""
import logging
import threading

from django.conf import settings

from .nodes.context import Contexto
from .nodes.if_node import _comparar

logger = logging.getLogger(__name__)

# Guard de re-entrância: bloqueia cascata de evento dentro do mesmo request/thread.
_local = threading.local()
_MAX_PROFUNDIDADE = 3

# Valores que vão pra `variaveis` (persistidas como JSON na fila) precisam ser
# JSON-serializáveis. Objetos de domínio (lead, conversa) entram só por entidade.
_ENTIDADES = ('lead', 'oportunidade', 'conversa')


def on_evento(evento, contexto, tenant):
    """Hook do sistema vivo: enfileira os fluxos que escutam `evento`. Blindado."""
    if not getattr(settings, 'AUTOMACAO_WIRING_ATIVO', False):
        return
    if not evento or tenant is None:
        return

    profundidade = getattr(_local, 'profundidade', 0)
    if profundidade >= _MAX_PROFUNDIDADE:
        logger.warning('automacao.on_evento: profundidade máx atingida (%s), ignorando %s', profundidade, evento)
        return

    _local.profundidade = profundidade + 1
    try:
        _despachar(evento, contexto or {}, tenant)
    except Exception:
        logger.exception('automacao.on_evento falhou (evento=%s)', evento)
    finally:
        _local.profundidade = profundidade


def _despachar(evento, contexto, tenant):
    from .models import Fluxo

    fluxos = list(
        Fluxo.all_tenants.filter(tenant=tenant, ativo=True, gatilho_evento=evento)
    )
    if not fluxos:
        return

    for fluxo in fluxos:
        try:
            trigger_handle, cfg = _achar_trigger(fluxo.grafo, evento)
            if trigger_handle is None:
                continue
            ctx = _contexto_do_evento(contexto, tenant)
            if not _filtros_passam(cfg.get('filtros') or [], ctx):
                continue
            lead = ctx.lead if _eh_lead(ctx.lead) else None
            if _freio_bloqueia(fluxo, lead, cfg):
                continue
            _enfileirar(fluxo, ctx, trigger_handle)
        except Exception:
            logger.exception('automacao: falha ao enfileirar fluxo %s (evento=%s)', fluxo.pk, evento)


def _achar_trigger(grafo, evento):
    """Acha (handle, config) do nó-gatilho de evento. (None, {}) se não houver."""
    nodes = (grafo or {}).get('nodes') or {}
    for handle, n in nodes.items():
        if n.get('tipo') == 'evento' and ((n.get('config') or {}).get('evento') or '') == evento:
            return handle, (n.get('config') or {})
    return None, {}


def _freio_bloqueia(fluxo, lead, cfg):
    """Freio por lead: True se o disparo deve ser barrado.

    - `cooldown_horas`: não dispara de novo pro mesmo lead dentro do intervalo.
    - `max_por_lead`: não dispara se o lead já atingiu o nº máximo de execuções.
    Sem lead ou sem freio configurado → nunca barra. Idempotência das ações de
    escrita + âncora de lead continuam valendo por cima disto.
    """
    def _int(v):
        try:
            return int(v or 0)
        except (ValueError, TypeError):
            return 0

    max_lead = _int(cfg.get('max_por_lead'))
    cooldown_h = _int(cfg.get('cooldown_horas'))
    if lead is None or (max_lead <= 0 and cooldown_h <= 0):
        return False

    from .models import ExecucaoFluxo
    qs = ExecucaoFluxo.all_tenants.filter(tenant=fluxo.tenant, fluxo=fluxo, lead=lead)
    if cooldown_h > 0:
        from datetime import timedelta
        from django.utils import timezone
        if qs.filter(criado_em__gte=timezone.now() - timedelta(hours=cooldown_h)).exists():
            return True
    if max_lead > 0 and qs.count() >= max_lead:
        return True
    return False


def _contexto_do_evento(contexto, tenant):
    """Monta o Contexto: entidades por objeto (templating) + escalares em variaveis."""
    variaveis = {
        k: v for k, v in contexto.items()
        if k not in _ENTIDADES and _serializavel(v)
    }
    return Contexto(
        tenant=tenant,
        lead=contexto.get('lead'),
        oportunidade=contexto.get('oportunidade'),
        conversa=contexto.get('conversa'),
        variaveis=variaveis,
    )


def _filtros_passam(filtros, ctx):
    """Todos os filtros precisam bater (AND). Reusa o `_comparar` do nó if."""
    for f in filtros or []:
        campo = (f.get('campo') or '').strip()
        operador = f.get('operador') or 'igual'
        if not campo:
            continue
        a = ctx.resolver('{{' + campo + '}}')
        b = ctx.resolver(f.get('valor', ''))
        if not _comparar(a, operador, b):
            return False
    return True


def _enfileirar(fluxo, ctx, trigger_handle):
    """Cria a execução PENDENTE (deferida). O cron roda fora do thread do evento."""
    from django.utils import timezone
    from .models import ExecucaoFluxo

    estado = {'variaveis': ctx.variaveis, 'nodes': {}, 'inicio': trigger_handle}
    ExecucaoFluxo(
        tenant=fluxo.tenant,
        fluxo=fluxo,
        status='pendente',
        estado=estado,
        lead=ctx.lead if _eh_lead(ctx.lead) else None,
        agendado_para=timezone.now(),
    ).save()


def _eh_lead(obj):
    """True se `obj` é um LeadProspecto (pra setar a FK; ignora outros objetos)."""
    if obj is None:
        return False
    try:
        from django.apps import apps as django_apps
        return isinstance(obj, django_apps.get_model('leads', 'LeadProspecto'))
    except Exception:
        return False


def _serializavel(v):
    return isinstance(v, (str, int, float, bool, type(None), list, dict))
