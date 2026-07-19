"""Interface comum dos executores de processos HubSoft.

Cada processo (conversão, novo serviço, upgrade) tem dois executores que
implementam esta interface: um via webdriver (Selenium) e um via API interna.
O `seletor` escolhe o primário e, se falhar, tenta o fallback.

Segurança: o guard `dry_run_efetivo()` força dry-run enquanto
`HUBSOFT_DRY_RUN_FORCADO=True` (default), independentemente do que o worker pedir.
Só CPFs na allowlist `HUBSOFT_CPFS_TESTE` podem executar de verdade.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from django.conf import settings


@dataclass
class ResultadoExecucao:
    status: str                 # 'sucesso' | 'falha' | 'dry_run'
    executor: str = ''          # 'api_interna' | 'webdriver'
    erro: str = ''
    etapa: str = ''
    metadados: dict = field(default_factory=dict)
    duracao_ms: int | None = None


def dry_run_efetivo(dry_run_pedido: bool, cpf: str | None = None) -> bool:
    """Decide se a execução roda em dry-run de fato.

    - Se o worker já pediu dry_run → dry-run.
    - Se HUBSOFT_DRY_RUN_FORCADO (default True) → dry-run, A NÃO SER que o CPF
      esteja na allowlist HUBSOFT_CPFS_TESTE (homologação caso a caso).
    """
    if dry_run_pedido:
        return True
    forcado = getattr(settings, 'HUBSOFT_DRY_RUN_FORCADO', True)
    if not forcado:
        return False
    allowlist = {
        ''.join(c for c in str(x) if c.isdigit())
        for x in getattr(settings, 'HUBSOFT_CPFS_TESTE', [])
    }
    cpf_d = ''.join(c for c in str(cpf or '') if c.isdigit())
    if cpf_d and cpf_d in allowlist:
        return False   # CPF liberado para execução real
    return True        # guard ativo → força dry-run


class Executor(ABC):
    nome: str = ''                  # 'api_interna' | 'webdriver'
    processo: str = ''              # 'conversao' | 'novo_servico' | 'upgrade'

    @abstractmethod
    def executar(self, registro_id: int, *, dry_run: bool) -> ResultadoExecucao:
        """Executa o processo para o registro. Deve respeitar dry-run e nunca
        levantar exceção — capturar e devolver ResultadoExecucao(status='falha')."""
        raise NotImplementedError
