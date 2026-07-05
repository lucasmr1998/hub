"""
Execução persistida + retoma.

A execução pode pausar de dois jeitos (NodeResult.espera):
- `timer`    → retoma quando o tempo vence (delay), pelo cron.
- `resposta` → retoma quando o contato responde (gancho do inbox), ou estoura o
  timeout (cron → segue a saída `timeout`).

`retomar(execucao, branch, dados)` continua a partir do **nó que pausou**, seguindo
`branch` — e injeta a resposta do contato quando há.

Hardening do cron (rodadas podem sobrepor):
- Claim atômico (E3): antes de processar uma execução o worker faz um CAS
  (`_claim`) que só uma rodada vence — duas rodadas concorrentes não rodam a
  mesma execução.
- Watchdog (E3): `destravar_execucoes_presas` devolve pra fila o que ficou
  `rodando` além do limite (worker morto no meio).
- Retry transitório (E4): erro NÃO tratado (branch erro não conectada) em nó
  seguro reenfileira com backoff, retomando DO NÓ QUE FALHOU, até um teto.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import ExecucaoFluxo
from .nodes import Contexto, tipo_por_slug
from .runtime import executar_fluxo, _proxima

logger = logging.getLogger(__name__)

# Retry transitório (E4): atrasos (segundos) de cada retentativa. O nº de posições
# é o teto de retentativas. Retoma do nó que falhou, não do início.
RETRY_BACKOFF_SEGUNDOS = [300, 900]
MAX_TENTATIVAS = len(RETRY_BACKOFF_SEGUNDOS)


def executar_e_persistir(fluxo, contexto, *, inicio=None, execucao=None):
    """Roda o grafo e persiste o ExecucaoFluxo. Devolve (execucao, RunResult)."""
    res = executar_fluxo(fluxo.grafo, contexto, inicio=inicio)
    trace = [
        {'handle': p.handle, 'tipo': p.tipo, 'status': p.status, 'branch': p.branch, 'erro': p.erro}
        for p in res.passos
    ]

    if execucao is None:
        execucao = ExecucaoFluxo(tenant=fluxo.tenant, fluxo=fluxo)
    execucao.trace = (execucao.trace or []) + trace
    execucao.erro = res.erro or ''

    if res.status == 'aguardando':
        execucao.status = 'aguardando'
        ag = res.aguardando or {}
        espera = ag.get('espera') or {}
        execucao.estado = ag.get('estado') or {}
        execucao.no_pausado = ag.get('no_pausado') or ''
        execucao.modo_espera = espera.get('tipo') or 'timer'
        execucao.chave = espera.get('chave') or ''
        segundos = espera.get('segundos') or 0
        execucao.agendado_para = (timezone.now() + timedelta(seconds=segundos)) if segundos else None
    elif (res.status == 'erro' and execucao.tentativas < MAX_TENTATIVAS
          and _no_seguro_pra_retry(fluxo, res)):
        # Erro NÃO tratado (branch erro não conectada) em nó seguro: reenfileira com
        # backoff, retomando DO NÓ QUE FALHOU (estado serializado no momento da falha).
        atraso = RETRY_BACKOFF_SEGUNDOS[execucao.tentativas]
        execucao.tentativas += 1
        execucao.status = 'pendente'
        execucao.estado = contexto.serializar()
        execucao.no_pausado = res.passos[-1].handle if res.passos else ''
        execucao.modo_espera = ''
        execucao.chave = ''
        execucao.claimed_em = None  # volta pra fila (não está mais reivindicada)
        execucao.agendado_para = timezone.now() + timedelta(seconds=atraso)
    else:
        # Completada/erro final: persiste o estado final (variaveis + nodes) pra
        # observabilidade — o editor reproduz a execução no canvas com o I/O por nó.
        execucao.status = res.status
        execucao.estado = contexto.serializar()
        execucao.agendado_para = None
        execucao.no_pausado = ''
        execucao.modo_espera = ''

    execucao.save()
    return execucao, res


def _no_seguro_pra_retry(fluxo, res):
    """True se o nó que falhou pode ser reexecutado automaticamente num retry.

    Olha o tipo do nó do último passo (`res.passos[-1]`) e devolve
    `no.retry_seguro`. Nó desconhecido ou sem passos → True (default seguro)."""
    if not res.passos:
        return True
    handle = res.passos[-1].handle
    definicao = ((fluxo.grafo.get('nodes') or {}).get(handle)) or {}
    no = tipo_por_slug(definicao.get('tipo'))
    if no is None:
        return True
    return getattr(no, 'retry_seguro', True)


def retomar(execucao, branch, dados=None, extra_vars=None):
    """Continua a execução a partir do nó pausado, seguindo `branch`.

    `dados` (ex: {'resposta': '...'}) é injetado: vira `{{nodes.<pausado>.resposta}}`
    e `{{var.resposta}}` pro resto do fluxo. `extra_vars` funde em `var.*` (ex:
    `modo_atendimento` atualizado, pra o fluxo re-checar pausa-por-humano na retoma).
    """
    contexto = _rehidratar(execucao)
    if extra_vars:
        contexto.variaveis.update(extra_vars)
    if dados:
        contexto.registrar_saida(execucao.no_pausado, dados)
        if 'resposta' in dados:
            contexto.variaveis['resposta'] = dados['resposta']

    proximo = _proxima(execucao.fluxo.grafo, execucao.no_pausado, branch)
    if not proximo:
        execucao.status = 'completado'
        execucao.agendado_para = None
        execucao.modo_espera = ''
        execucao.save(update_fields=['status', 'agendado_para', 'modo_espera', 'atualizado_em'])
        return execucao

    execucao, _res = executar_e_persistir(execucao.fluxo, contexto, inicio=proximo, execucao=execucao)
    return execucao


def _claim(pk, de):
    """CAS: `de` -> 'rodando'. True só pro worker que venceu a corrida (rowcount==1)."""
    n = ExecucaoFluxo.all_tenants.filter(pk=pk, status=de).update(
        status='rodando', claimed_em=timezone.now())
    return n == 1


def destravar_execucoes_presas(minutos=None):
    """Watchdog: devolve pra fila o que ficou `rodando` além do limite.

    Um worker que morre no meio deixa a execução travada em 'rodando'. Passado o
    limite (`AUTOMACAO_WATCHDOG_MINUTOS`, default 10), volta pro status de origem:
    `modo_espera` preenchido → 'aguardando' (pausa por resposta/timer); vazio →
    'pendente'. Ambos com `agendado_para=now` e `claimed_em=None` (fila limpa).
    Devolve o total destravado."""
    limite = minutos if minutos is not None else getattr(settings, 'AUTOMACAO_WATCHDOG_MINUTOS', 10)
    agora = timezone.now()
    corte = agora - timedelta(minutes=limite)
    base = ExecucaoFluxo.all_tenants.filter(status='rodando', claimed_em__lte=corte)
    # Preso após uma pausa (tinha modo_espera) volta pra 'aguardando'; senão 'pendente'.
    presos_aguardando = base.exclude(modo_espera='').update(
        status='aguardando', agendado_para=agora, claimed_em=None)
    presos_pendentes = base.filter(modo_espera='').update(
        status='pendente', agendado_para=agora, claimed_em=None)
    total = presos_aguardando + presos_pendentes
    if total:
        logger.warning('automacao: watchdog destravou %s execução(ões) presa(s) em "rodando"', total)
    return total


def retomar_pendentes(limite=100):
    """Cron: retoma o que venceu — timer (resume normal) ou resposta (timeout).

    Claim atômico por execução (`_claim`): duas rodadas concorrentes não retomam a
    mesma. Só processa o que este worker reivindicou (`aguardando` -> `rodando`)."""
    agora = timezone.now()
    pks = list(
        ExecucaoFluxo.all_tenants
        .filter(status='aguardando', agendado_para__lte=agora)
        .values_list('pk', flat=True)[:limite]
    )
    n = 0
    for pk in pks:
        if not _claim(pk, 'aguardando'):
            continue  # outra rodada venceu a corrida
        ex = (
            ExecucaoFluxo.all_tenants.select_related('fluxo', 'tenant')
            .filter(pk=pk).first()
        )
        if ex is None:
            continue
        branch = 'timeout' if ex.modo_espera == 'resposta' else 'default'
        retomar(ex, branch)
        n += 1
    return n


def rodar_novos(limite=100):
    """Cron: roda as execuções enfileiradas por gatilho (status `pendente`, deferido).

    O fluxo roda AQUI (no cron), fora do thread do evento que só enfileirou. Cada
    execução é isolada: uma falha não derruba as outras.

    Claim atômico por execução (`_claim`): duas rodadas concorrentes nunca rodam a
    mesma. Watchdog no início devolve pra fila o que ficou preso em 'rodando'.
    """
    destravar_execucoes_presas()
    agora = timezone.now()
    pks = list(
        ExecucaoFluxo.all_tenants
        .filter(status='pendente', agendado_para__lte=agora)
        .values_list('pk', flat=True)[:limite]
    )
    n = 0
    for pk in pks:
        if not _claim(pk, 'pendente'):
            continue  # outra rodada venceu a corrida
        ex = (
            ExecucaoFluxo.all_tenants.select_related('fluxo', 'tenant', 'lead')
            .filter(pk=pk).first()
        )
        if ex is None:
            continue
        try:
            contexto = _rehidratar(ex)
            # pendente-retry usa o nó que falhou (no_pausado); pendente novo, o estado.inicio.
            inicio = ex.no_pausado or (ex.estado or {}).get('inicio')
            executar_e_persistir(ex.fluxo, contexto, inicio=inicio, execucao=ex)
            n += 1
        except Exception:
            logger.exception('automacao: falha ao rodar execução pendente %s', ex.pk)
            ex.status = 'erro'
            ex.erro = 'falha ao rodar execução enfileirada'
            ex.save(update_fields=['status', 'erro', 'atualizado_em'])
    return n


def retomar_por_resposta(tenant, chave, conteudo, modo_atendimento=None):
    """Inbox: o contato `chave` respondeu — retoma a execução pausada por ele.

    `modo_atendimento` (estado atual da conversa) é promovido em `var.modo_atendimento`
    pra o fluxo re-checar pausa-por-humano na retoma (o `_rehidratar` não restaura a
    entidade conversa).
    """
    if not chave or tenant is None:
        return False
    ex = (
        ExecucaoFluxo.all_tenants.select_related('fluxo', 'tenant')
        .filter(tenant=tenant, status='aguardando', modo_espera='resposta', chave=chave)
        .order_by('-criado_em').first()
    )
    if ex is None:
        return False
    extra = {'modo_atendimento': modo_atendimento} if modo_atendimento else None
    retomar(ex, 'resposta', {'resposta': conteudo}, extra_vars=extra)
    return True


def _rehidratar(execucao):
    """Re-hidrata o Contexto de uma execução. Restaura o lead pela FK; oportunidade/
    conversa como entidade ficam como follow-up (seus subcampos são `var.*`)."""
    estado = execucao.estado or {}
    return Contexto(
        tenant=execucao.tenant,
        lead=execucao.lead,
        variaveis=estado.get('variaveis'),
        nodes=estado.get('nodes'),
    )
