"""Seleção de executor + fallback + auditoria.

Lê a estratégia por processo de `settings.HUBSOFT_AUTOMACAO` (primário + fallback),
roda o primário e, se falhar (fora de dry-run), tenta o fallback uma vez. Cada
tentativa vira um `ExecucaoHubsoft`.
"""
from __future__ import annotations

from django.conf import settings

from .base import ResultadoExecucao
from ..models import ExecucaoHubsoft


def _instanciar(processo: str, nome_executor: str, **kw):
    if processo == 'novo_servico':
        from .novo_servico import ExecutorWebdriverNovoServico
        if nome_executor == 'webdriver':
            return ExecutorWebdriverNovoServico(**kw)
        if nome_executor == 'api_interna':
            from .novo_servico_api import ExecutorApiNovoServico  # Fase 2
            return ExecutorApiNovoServico(**kw)
    if processo == 'upgrade':
        if nome_executor == 'webdriver':
            from .upgrade import ExecutorWebdriverUpgrade
            return ExecutorWebdriverUpgrade(**kw)
        if nome_executor == 'api_interna':
            from .upgrade_api import ExecutorApiUpgrade
            return ExecutorApiUpgrade(**kw)
    if processo == 'conversao':
        if nome_executor == 'webdriver':
            from .conversao import ExecutorWebdriverConversao  # Fase 4
            return ExecutorWebdriverConversao(**kw)
        if nome_executor == 'api_interna':
            from .conversao_api import ExecutorApiConversao
            return ExecutorApiConversao(**kw)
    raise ValueError(f'executor {nome_executor!r} indisponível p/ {processo!r}')


def _auditar(processo, registro_id, res: ResultadoExecucao, dry_run, fallback):
    try:
        ExecucaoHubsoft.objects.create(
            processo=processo, registro_id=registro_id,
            executor=res.executor or '?', status=res.status, dry_run=dry_run,
            tentativa_fallback=fallback, etapa=res.etapa, erro=res.erro,
            metadados=res.metadados or {}, duracao_ms=res.duracao_ms,
        )
    except Exception:
        pass


def processar(processo: str, registro_id: int, *, dry_run: bool,
              executor_forcado: str | None = None, **kw) -> ResultadoExecucao:
    """Executa o processo com primário e fallback. Retorna o resultado final."""
    cfg = settings.HUBSOFT_AUTOMACAO.get(processo, {})
    primario = executor_forcado or cfg.get('estrategia', 'webdriver')
    fallback = None if executor_forcado else cfg.get('fallback')

    res = _instanciar(processo, primario, **kw).executar(registro_id, dry_run=dry_run)
    _auditar(processo, registro_id, res, dry_run, fallback=False)

    # fallback só se o primário FALHOU de verdade (não em dry-run)
    if res.status == 'falha' and fallback and not dry_run:
        res2 = _instanciar(processo, fallback, **kw).executar(registro_id, dry_run=dry_run)
        _auditar(processo, registro_id, res2, dry_run, fallback=True)
        if res2.status in ('sucesso', 'dry_run'):
            return res2
    return res
