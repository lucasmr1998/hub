"""Executor de UPGRADE via API interna do HubSoft (migração rápida ~15s).

Descoberto por captura CDP (hubsoft_capturar_migracao): a migração é um
POST /api/v1/cliente/servico igual ao de NOVO SERVIÇO, só que com os campos de
migração: id_cliente_servico_antigo + executar_migracao_imediata +
migrar_durante_troca_servico, e o serviço já nasce 'servico_habilitado'.

Por isso reaproveitamos o MESMO construtor de payload do novo serviço
(montar_payload_adicionar_servico, já validado) e só acrescentamos esses campos.
No dry-run monta o payload mas não faz o POST.
"""
from __future__ import annotations

import time

from .base import Executor, ResultadoExecucao, dry_run_efetivo
from .upgrade import _cpf_do_upgrade, _planos_permitidos_upgrade
from ..services.ambiente import preparar_ambiente_webdriver

MIGRACAO_FLAGS = {'atendimentosOS': True,
                  'tipoMigracaoAtendimentoOs': 'atendimento_com_os_aberta'}


class ExecutorApiUpgrade(Executor):
    nome = 'api_interna'
    processo = 'upgrade'

    def __init__(self, *, headless: bool = True, **_):
        self.headless = headless

    def executar(self, registro_id: int, *, dry_run: bool) -> ResultadoExecucao:
        t0 = time.time()
        cli = None
        etapa = 'init'
        try:
            from vendas_web.models import UpgradePlano
            up = UpgradePlano.objects.get(pk=registro_id)

            permitidos = _planos_permitidos_upgrade()
            if permitidos and str(up.id_plano_novo) not in permitidos:
                return ResultadoExecucao(
                    status='falha', executor=self.nome, etapa='validar_plano',
                    erro=f'plano {up.id_plano_novo} não disponível para upgrade '
                         f'(permitidos: {sorted(permitidos)})',
                    duracao_ms=int((time.time() - t0) * 1000))

            dry = dry_run_efetivo(dry_run, _cpf_do_upgrade(registro_id))
            preparar_ambiente_webdriver()

            etapa = 'buscar_dados'
            from ..webdriver.main_upgrade_plano import buscar_dados
            dados = buscar_dados(registro_id)   # id_cliente_hubsoft, id_cliente_servico (antigo)

            from ..api_interna.cliente_http import ClienteHTTP
            cli = ClienteHTTP(headless=self.headless)
            etapa = 'login'
            cli.login()

            etapa = 'resolver_endereco'
            cl = cli.get_cliente(dados.id_cliente_hubsoft)
            enderecos = cl.get('enderecos') or []
            end_cad = next((e for e in enderecos
                            if (e.get('pivot') or {}).get('tipo') == 'cadastral'),
                           enderecos[0] if enderecos else {})
            id_endereco_numero = end_cad.get('id_endereco_numero')
            end = end_cad.get('endereco_numero') or end_cad

            etapa = 'resolver_dados'
            antigo = cli.obter_servico_edit(up.id_cliente_servico)
            id_vencimento = antigo.get('id_vencimento') or 9
            id_servico_novo = int(up.id_plano_novo)
            plano = cli.buscar_plano_por_id(id_servico_novo)
            valor = float(plano.get('valor') or 0)

            etapa = 'montar_payload'
            payload = cli.montar_payload_adicionar_servico(
                id_cliente=dados.id_cliente_hubsoft,
                id_endereco_numero=id_endereco_numero, endereco_numero_obj=end,
                id_servico=id_servico_novo, valor=valor, id_vencimento=id_vencimento)
            # ── campos que tornam o POST uma MIGRAÇÃO (não um novo serviço) ──
            payload['id_cliente_servico_antigo'] = up.id_cliente_servico
            payload['executar_migracao_imediata'] = True
            payload['migrar_durante_troca_servico'] = dict(MIGRACAO_FLAGS)
            payload['servico_status'] = dict(cli.SERVICO_STATUS_HABILITADO)
            payload['id_servico_status'] = 11

            resumo = {'id_cliente_servico_antigo': up.id_cliente_servico,
                      'id_servico_novo': id_servico_novo, 'valor': valor,
                      'id_endereco_numero': id_endereco_numero}
            if dry:
                return ResultadoExecucao(status='dry_run', executor=self.nome,
                                         etapa='payload_montado', metadados=resumo,
                                         duracao_ms=int((time.time() - t0) * 1000))

            etapa = 'migrar'
            resp = cli._post('/api/v1/cliente/servico', payload)
            j = resp.json() if resp.content else {}
            if not resp.ok or j.get('status') != 'success':
                raise RuntimeError(f'migração falhou: {resp.status_code} {resp.text[:300]}')
            resumo['id_cliente_servico_novo'] = (j.get('cliente_servico') or {}).get('id_cliente_servico')
            return ResultadoExecucao(status='sucesso', executor=self.nome, etapa='fim',
                                     metadados=resumo, duracao_ms=int((time.time() - t0) * 1000))
        except Exception as e:  # noqa: BLE001
            return ResultadoExecucao(status='falha', executor=self.nome, etapa=etapa,
                                     erro=f'{type(e).__name__}: {e}'[:500],
                                     duracao_ms=int((time.time() - t0) * 1000))
        finally:
            if cli is not None:
                cli.close()
