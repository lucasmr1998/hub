"""
Execução persistida + retoma.

A execução pode pausar de dois jeitos (NodeResult.espera):
- `timer`    → retoma quando o tempo vence (delay), pelo cron.
- `resposta` → retoma quando o contato responde (gancho do inbox), ou estoura o
  timeout (cron → segue a saída `timeout`).

`retomar(execucao, branch, dados)` continua a partir do **nó que pausou**, seguindo
`branch` — e injeta a resposta do contato quando há.
"""
from datetime import timedelta

from django.utils import timezone

from .models import ExecucaoFluxo
from .nodes import Contexto
from .runtime import executar_fluxo, _proxima


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
        execucao.agendado_para = None
        execucao.no_pausado = ''
        execucao.modo_espera = ''

    execucao.save()
    return execucao, res


def retomar(execucao, branch, dados=None):
    """Continua a execução a partir do nó pausado, seguindo `branch`.

    `dados` (ex: {'resposta': '...'}) é injetado: vira `{{nodes.<pausado>.resposta}}`
    e `{{var.resposta}}` pro resto do fluxo.
    """
    contexto = _rehidratar(execucao.estado, execucao.tenant)
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


def retomar_por_resposta(tenant, chave, conteudo):
    """Inbox: o contato `chave` respondeu — retoma a execução pausada por ele."""
    if not chave or tenant is None:
        return False
    ex = (
        ExecucaoFluxo.all_tenants.select_related('fluxo', 'tenant')
        .filter(tenant=tenant, status='aguardando', modo_espera='resposta', chave=chave)
        .order_by('-criado_em').first()
    )
    if ex is None:
        return False
    retomar(ex, 'resposta', {'resposta': conteudo})
    return True


def _rehidratar(estado, tenant):
    estado = estado or {}
    return Contexto(tenant=tenant, variaveis=estado.get('variaveis'), nodes=estado.get('nodes'))
