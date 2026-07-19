"""Executores do processo NOVO SERVIÇO.

- ExecutorWebdriverNovoServico: embrulha o `executar()` portado (Selenium).
- ExecutorApiNovoServico: implementado na Fase 2 (API interna).
"""
from __future__ import annotations

import time

from .base import Executor, ResultadoExecucao, dry_run_efetivo
from ..services.ambiente import preparar_ambiente_webdriver


def _cpf_do_new_service(registro_id):
    """Resolve o CPF do cliente do NewService (para o guard de allowlist)."""
    try:
        from vendas_web.models import NewService
        ns = NewService.objects.select_related('lead').filter(pk=registro_id).first()
        return (ns.lead.cpf_cnpj if ns and ns.lead else '') or ''
    except Exception:
        return ''


class ExecutorWebdriverNovoServico(Executor):
    nome = 'webdriver'
    processo = 'novo_servico'

    def __init__(self, *, headless: bool = True, vendedor: str = 'Venda-Automática-Matrix',
                 grupo: str = 'Varejo', banco: str = 'BANCO ITAU'):
        self.headless = headless
        self.vendedor = vendedor
        self.grupo = grupo
        self.banco = banco

    def executar(self, registro_id: int, *, dry_run: bool) -> ResultadoExecucao:
        dry = dry_run_efetivo(dry_run, _cpf_do_new_service(registro_id))
        t0 = time.time()
        try:
            preparar_ambiente_webdriver()
            from ..webdriver.main_novo_servico import executar as wd_executar
            res = wd_executar(
                new_service_id=registro_id,
                vendedor=self.vendedor, grupo=self.grupo, banco=self.banco,
                headless=self.headless, dry_run=dry,
            )
            return ResultadoExecucao(
                status=res.get('status', 'falha'),
                executor=self.nome,
                erro=res.get('erro', ''),
                etapa=res.get('etapa', ''),
                metadados={k: res.get(k) for k in ('nome_cliente', 'id_cliente_hubsoft')
                           if res.get(k) is not None},
                duracao_ms=int((time.time() - t0) * 1000),
            )
        except SystemExit as e:   # buscar_dados levanta SystemExit em dados ausentes
            return ResultadoExecucao(status='falha', executor=self.nome,
                                     erro=f'dados: {e}', etapa='buscar_dados',
                                     duracao_ms=int((time.time() - t0) * 1000))
        except Exception as e:    # noqa: BLE001
            return ResultadoExecucao(status='falha', executor=self.nome,
                                     erro=f'{type(e).__name__}: {e}'[:500], etapa='executor',
                                     duracao_ms=int((time.time() - t0) * 1000))
