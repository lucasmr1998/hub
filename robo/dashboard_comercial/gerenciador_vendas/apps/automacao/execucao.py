"""
Execução persistida + retoma.

A execução pode pausar de dois jeitos (NodeResult.espera):
- `timer`    → retoma quando o tempo vence (delay), pelo cron.
- `resposta` → retoma quando o contato responde (gancho do inbox), ou estoura o
  timeout (cron → segue a saída `timeout`).

`retomar(execucao, branch, dados)` continua a partir do **nó que pausou**, seguindo
`branch` — e injeta a resposta do contato quando há.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from .models import ExecucaoFluxo
from .nodes import Contexto
from .runtime import executar_fluxo, _proxima

logger = logging.getLogger(__name__)


def executar_e_persistir(fluxo, contexto, *, inicio=None, execucao=None):
    """Roda o grafo e persiste o ExecucaoFluxo. Devolve (execucao, RunResult)."""
    res = executar_fluxo(fluxo.grafo, contexto, inicio=inicio)
    trace = [
        {'handle': p.handle, 'tipo': p.tipo, 'status': p.status, 'branch': p.branch, 'erro': p.erro}
        for p in res.passos
    ]

    if execucao is None:
        execucao = ExecucaoFluxo(tenant=fluxo.tenant, fluxo=fluxo)
    execucao.status = res.status
    execucao.trace = (execucao.trace or []) + trace
    execucao.erro = res.erro or ''

    if res.status == 'aguardando':
        ag = res.aguardando or {}
        espera = ag.get('espera') or {}
        execucao.estado = ag.get('estado') or {}
        execucao.no_pausado = ag.get('no_pausado') or ''
        execucao.modo_espera = espera.get('tipo') or 'timer'
        execucao.chave = espera.get('chave') or ''
        segundos = espera.get('segundos') or 0
        execucao.agendado_para = (timezone.now() + timedelta(seconds=segundos)) if segundos else None
    else:
        # Completada/erro: persiste o estado final (variaveis + nodes) pra observabilidade
        # — o editor reproduz a execução no canvas com o I/O por nó (estilo n8n).
        execucao.estado = contexto.serializar()
        execucao.agendado_para = None
        execucao.no_pausado = ''
        execucao.modo_espera = ''

    execucao.save()
    return execucao, res


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


def retomar_pendentes(limite=100):
    """Cron: retoma o que venceu — timer (resume normal) ou resposta (timeout)."""
    agora = timezone.now()
    pendentes = list(
        ExecucaoFluxo.all_tenants.select_related('fluxo', 'tenant')
        .filter(status='aguardando', agendado_para__lte=agora)[:limite]
    )
    n = 0
    for ex in pendentes:
        branch = 'timeout' if ex.modo_espera == 'resposta' else 'default'
        retomar(ex, branch)
        n += 1
    return n


def rodar_novos(limite=100):
    """Cron: roda as execuções enfileiradas por gatilho (status `pendente`, deferido).

    O fluxo roda AQUI (no cron), fora do thread do evento que só enfileirou. Cada
    execução é isolada: uma falha não derruba as outras.
    """
    agora = timezone.now()
    novos = list(
        ExecucaoFluxo.all_tenants.select_related('fluxo', 'tenant', 'lead')
        .filter(status='pendente', agendado_para__lte=agora)[:limite]
    )
    n = 0
    for ex in novos:
        try:
            contexto = _rehidratar(ex)
            inicio = (ex.estado or {}).get('inicio')
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
