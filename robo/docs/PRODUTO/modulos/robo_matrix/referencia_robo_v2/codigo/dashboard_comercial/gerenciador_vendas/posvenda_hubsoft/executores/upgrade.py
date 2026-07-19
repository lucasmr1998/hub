"""Executor de UPGRADE DE PLANO (webdriver — "Migrar para Outro Serviço").

A migração não tem endpoint de API interna conhecido (não capturado), então o
upgrade é só via webdriver por enquanto. O caminho API pode ser adicionado depois
capturando o endpoint de migração com hubsoft_capturar_apis.
"""
from __future__ import annotations

import time

from .base import Executor, ResultadoExecucao, dry_run_efetivo
from ..services.ambiente import preparar_ambiente_webdriver


def _cpf_do_upgrade(registro_id):
    try:
        from vendas_web.models import UpgradePlano
        up = UpgradePlano.objects.select_related('lead').filter(pk=registro_id).first()
        return (up.lead.cpf_cnpj if up and up.lead else '') or ''
    except Exception:
        return ''


def _planos_permitidos_upgrade():
    """Planos que o upgrade pode usar = os mesmos da vitrine (PlanoInternet ativos).
    Hoje: 620 Mega (1649), 1 Giga (1648), 1 Giga + Ponto Adicional (2088)."""
    from vendas_web.models import PlanoInternet
    return {str(x) for x in PlanoInternet.objects.filter(ativo=True)
            .values_list('id_sistema_externo', flat=True) if x}


class ExecutorWebdriverUpgrade(Executor):
    nome = 'webdriver'
    processo = 'upgrade'

    def __init__(self, *, headless: bool = True, vendedor: str = 'Venda-Automática-Matrix'):
        self.headless = headless
        self.vendedor = vendedor

    def executar(self, registro_id: int, *, dry_run: bool) -> ResultadoExecucao:
        dry = dry_run_efetivo(dry_run, _cpf_do_upgrade(registro_id))
        t0 = time.time()
        try:
            # Só permite upgrade para os planos que disponibilizamos (vitrine).
            from vendas_web.models import UpgradePlano
            up = UpgradePlano.objects.get(pk=registro_id)
            permitidos = _planos_permitidos_upgrade()
            if permitidos and str(up.id_plano_novo) not in permitidos:
                return ResultadoExecucao(
                    status='falha', executor=self.nome, etapa='validar_plano',
                    erro=f'plano {up.id_plano_novo} não disponível para upgrade '
                         f'(permitidos: {sorted(permitidos)})',
                    duracao_ms=int((time.time() - t0) * 1000))

            preparar_ambiente_webdriver()
            from ..webdriver.main_upgrade_plano import executar as wd_executar
            res = wd_executar(
                upgrade_id=registro_id, vendedor=self.vendedor,
                headless=self.headless, dry_run=dry,
            )
            return ResultadoExecucao(
                status=res.get('status', 'falha'), executor=self.nome,
                erro=res.get('erro', ''), etapa=res.get('etapa', ''),
                metadados={k: res.get(k) for k in ('nome_cliente', 'id_cliente_hubsoft')
                           if res.get(k) is not None},
                duracao_ms=int((time.time() - t0) * 1000))
        except SystemExit as e:
            return ResultadoExecucao(status='falha', executor=self.nome,
                                     erro=f'dados: {e}', etapa='buscar_dados',
                                     duracao_ms=int((time.time() - t0) * 1000))
        except Exception as e:  # noqa: BLE001
            return ResultadoExecucao(status='falha', executor=self.nome,
                                     erro=f'{type(e).__name__}: {e}'[:500], etapa='executor',
                                     duracao_ms=int((time.time() - t0) * 1000))
