"""
Camada de gatilho unificada — dispatch de evento do sistema p/ a engine.

`on_evento(evento, contexto, tenant)` é o ponto único: achado pelo hook blindado
no `disparar_evento` do motor de marketing (onde TODOS os eventos já passam),
encontra os fluxos que escutam aquele evento, avalia os filtros e **enfileira**
a execução (status `pendente`). Quem roda o fluxo é o cron (`rodar_novos`), fora
do thread do evento — o evento nunca espera. (Modelo deferido: não sobrecarrega.)

Além do gatilho por evento, existe o gatilho **agenda** (varredura): em vez de
reagir a um evento do sistema, `despachar_agendas` roda em ciclo (cron próprio,
`automacao_despachar_agendas`) e, pro fluxo cujo intervalo já venceu, executa uma
`varredura` (registry em `varreduras.py`) que busca N itens no banco/API externa —
cada item vira UMA execução enfileirada, com os mesmos freios do gatilho por evento.

Segurança:
- Kill-switch `settings.AUTOMACAO_WIRING_ATIVO` (liga/desliga sem deploy).
- Tudo por tenant explícito (a engine roda fora de request).
- Tudo embrulhado: uma falha aqui NUNCA quebra o motor que disparou o evento.
- Guard de re-entrância (thread-local) contra cascata no mesmo request.
- Orçamento global (hardening E5, `_orcamento_excedido`): teto por hora, default
  on, contra loop entre ciclos de cron (fluxo reenfileirando a si mesmo via
  evento). Independente do guard acima, que só protege o mesmo request.
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
            if _orcamento_excedido(fluxo, lead):
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


# ============================================================================
# GATILHO AGENDA (varredura) — dispatcher em ciclo, não por evento
# ============================================================================

def despachar_agendas(agora=None):
    """Cron (`automacao_despachar_agendas`): dispara as rodadas de varredura vencidas.

    Candidato = `Fluxo` ativo com `agenda_intervalo_minutos` preenchido (índice
    sincronizado do grafo em `Fluxo.save()`). Cada fluxo roda no máximo 1 rodada
    por chamada (CAS em `_rodar_agenda_do_fluxo`, que também decide se o intervalo
    já venceu). Devolve o total de execuções enfileiradas na chamada."""
    if not getattr(settings, 'AUTOMACAO_WIRING_ATIVO', False):
        return 0

    from django.utils import timezone
    from .models import Fluxo

    agora = agora or timezone.now()
    candidatos = list(
        Fluxo.all_tenants.filter(ativo=True, agenda_intervalo_minutos__isnull=False)
        .select_related('tenant')
    )
    total = 0
    for fluxo in candidatos:
        try:
            total += _rodar_agenda_do_fluxo(fluxo, agora)
        except Exception:
            logger.exception('automacao: falha na rodada de agenda do fluxo %s', fluxo.pk)
    return total


def _rodar_agenda_do_fluxo(fluxo, agora):
    """Roda (no máximo) 1 rodada de varredura do fluxo, se o intervalo já venceu.

    Claim atômico (CAS) em `agenda_ultima_rodada`, ANTES de varrer: só o worker
    que vence a corrida executa a rodada — duas chamadas concorrentes sobre o
    mesmo fluxo nunca varrem duas vezes. Devolve o nº de execuções enfileiradas
    nesta rodada (0 se não venceu / sem trigger / sem varredura / sem freio / erro).
    """
    intervalo = fluxo.agenda_intervalo_minutos or 0
    if intervalo <= 0:
        return 0

    from datetime import timedelta

    from .models import Fluxo

    ultima = fluxo.agenda_ultima_rodada
    if ultima is not None and ultima + timedelta(minutes=intervalo) > agora:
        return 0

    # CAS: só quem vence a corrida (rowcount==1) executa esta rodada.
    n = (
        Fluxo.all_tenants.filter(pk=fluxo.pk, agenda_ultima_rodada=ultima)
        .update(agenda_ultima_rodada=agora)
    )
    if n != 1:
        return 0

    trigger_handle, cfg = _achar_trigger_agenda(fluxo.grafo)
    if trigger_handle is None:
        return 0

    from .varreduras import VARREDURAS
    fn = VARREDURAS.get(cfg.get('varredura'))
    if fn is None:
        return 0

    def _int(v):
        try:
            return int(v or 0)
        except (ValueError, TypeError):
            return 0

    if _int(cfg.get('max_por_lead')) <= 0 and _int(cfg.get('cooldown_horas')) <= 0:
        logger.warning('automacao: agenda do fluxo %s sem freio, pulando rodada', fluxo.pk)
        return 0

    try:
        itens = fn(fluxo.tenant, cfg.get('varredura_config') or {}) or []
    except Exception:
        logger.exception('automacao: falha ao rodar varredura %r (fluxo=%s)', cfg.get('varredura'), fluxo.pk)
        return 0

    max_por_rodada = _int(cfg.get('max_por_rodada')) or 25

    contador = 0
    for item in itens:
        if contador >= max_por_rodada:
            break
        if not isinstance(item, dict):
            continue
        try:
            ctx = _contexto_do_evento(item, fluxo.tenant)
            lead = ctx.lead if _eh_lead(ctx.lead) else None
            if _freio_bloqueia(fluxo, lead, cfg) or _orcamento_excedido(fluxo, lead):
                continue
            _enfileirar(fluxo, ctx, trigger_handle)
            contador += 1
        except Exception:
            logger.exception(
                'automacao: falha ao enfileirar item de varredura %r (fluxo=%s)',
                cfg.get('varredura'), fluxo.pk,
            )
    return contador


def _achar_trigger_agenda(grafo):
    """Acha (handle, config) do nó-gatilho `agenda`. (None, {}) se não houver."""
    nodes = (grafo or {}).get('nodes') or {}
    for handle, n in nodes.items():
        if n.get('tipo') == 'agenda':
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


def _orcamento_excedido(fluxo, lead):
    """Teto GLOBAL de execuções por hora, default-on e independente da config do fluxo.

    O `_freio_bloqueia` acima é opcional (por fluxo) e o guard de profundidade em
    `on_evento` é thread-local (só protege dentro do mesmo request). Nenhum dos
    dois barra o caso: fluxo dispara uma ação que gera um evento que reenfileira
    o próprio fluxo, formando um loop que atravessa ciclos de cron (a execução é
    deferida). Este teto cobre esse buraco, por janela de 1 hora.

    `AUTOMACAO_ORCAMENTO_LEAD_HORA` / `AUTOMACAO_ORCAMENTO_FLUXO_HORA` <= 0
    desliga cada limite independentemente.
    """
    max_lead = int(getattr(settings, 'AUTOMACAO_ORCAMENTO_LEAD_HORA', 0) or 0)
    max_fluxo = int(getattr(settings, 'AUTOMACAO_ORCAMENTO_FLUXO_HORA', 0) or 0)
    if max_lead <= 0 and max_fluxo <= 0:
        return False

    from datetime import timedelta
    from django.utils import timezone
    from .models import ExecucaoFluxo

    def _logar(motivo, contagem, limite):
        try:
            from apps.sistema.models import LogSistema
            LogSistema.all_tenants.create(
                tenant=fluxo.tenant,
                categoria='sistema', acao='automacao_freio_global',
                entidade='Fluxo', entidade_id=fluxo.pk,
                mensagem=(
                    f'Fluxo {fluxo.pk} barrado pelo orçamento global ({motivo}): '
                    f'{contagem}/{limite} execuções na última hora.'
                ),
                dados_extras={
                    'motivo': motivo, 'contagem': contagem, 'limite': limite,
                    'lead_id': lead.pk if lead is not None else None,
                },
            )
        except Exception:
            logger.exception('automacao: falha ao registrar freio global (fluxo=%s)', fluxo.pk)

    base = ExecucaoFluxo.all_tenants.filter(
        tenant=fluxo.tenant, fluxo=fluxo,
        criado_em__gte=timezone.now() - timedelta(hours=1),
    )

    if lead is not None and max_lead > 0:
        contagem = base.filter(lead=lead).count()
        if contagem >= max_lead:
            _logar('lead', contagem, max_lead)
            return True

    if max_fluxo > 0:
        contagem = base.count()
        if contagem >= max_fluxo:
            _logar('fluxo', contagem, max_fluxo)
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
    """Cria a execução PENDENTE (deferida). O cron roda fora do thread do evento.

    O `estado` persiste também as ENTIDADES por id (`Contexto.serializar()`), pra
    o `execucao._rehidratar` restaurar `oportunidade`/`conversa` na hora de rodar —
    sem isso, nós de CRM (criar_nota, mover_estagio, reabrir...) falhariam no
    caminho da fila por falta de `contexto.oportunidade`."""
    from django.utils import timezone
    from .models import ExecucaoFluxo

    estado = {**ctx.serializar(), 'inicio': trigger_handle}
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
