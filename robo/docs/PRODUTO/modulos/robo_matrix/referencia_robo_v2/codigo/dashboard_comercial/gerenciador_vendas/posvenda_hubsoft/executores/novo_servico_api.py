"""Executor de NOVO SERVIÇO via API interna do HubSoft (caminho rápido ~10s).

Orquestra o `ClienteHTTP` portado: login (Selenium → Bearer) → resolve endereço/
plano/vencimento → monta o payload (template capturado) → adiciona o serviço +
habilita. No dry-run resolve tudo e monta o payload, mas NÃO faz o POST de criação
do serviço (o passo que cria de fato).
"""
from __future__ import annotations

import time

from .base import Executor, ResultadoExecucao, dry_run_efetivo
from .novo_servico import _cpf_do_new_service
from ..services.ambiente import preparar_ambiente_webdriver


class ExecutorApiNovoServico(Executor):
    nome = 'api_interna'
    processo = 'novo_servico'

    def __init__(self, *, headless: bool = True, **_):
        self.headless = headless

    def executar(self, registro_id: int, *, dry_run: bool) -> ResultadoExecucao:
        dry = dry_run_efetivo(dry_run, _cpf_do_new_service(registro_id))
        t0 = time.time()
        cli = None
        etapa = 'init'
        try:
            from vendas_web.models import NewService
            ns = NewService.objects.get(pk=registro_id)

            preparar_ambiente_webdriver()
            etapa = 'buscar_dados'
            from ..webdriver.main_novo_servico import buscar_dados
            dados = buscar_dados(registro_id)   # resolve id_cliente, dia, endereço

            from ..api_interna.cliente_http import ClienteHTTP
            cli = ClienteHTTP(headless=self.headless)
            etapa = 'login'
            cli.login()

            etapa = 'resolver_endereco'
            # Endereço da INSTALAÇÃO = o que o cliente informou para ESTE serviço
            # (NewService), não o cadastral do cliente. Se o NewService tem endereço
            # próprio, resolve (reusa se já existir, senão cria com id=None — o POST
            # do serviço cria); senão cai no cadastral.
            id_endereco_numero, end = None, None
            if (ns.cep or '').strip() and (ns.rua or '').strip():
                cep_data = cli.buscar_cep(ns.cep)
                cidade_obj = (cep_data or {}).get('cidade_completo') or {}
                res = cli.resolver_endereco_numero(
                    ns.cep, cidade_obj, ns.bairro or '', ns.rua,
                    str(ns.numero_residencia or 'S/N'))
                nums = res.get('numeros') or []
                if nums:                       # endereço já existe → reusa
                    id_endereco_numero = nums[0].get('id_endereco_numero')
                    end = nums[0]
                else:                          # novo → cria no POST do serviço
                    end = {
                        'id_endereco_numero': None,
                        'numero': str(ns.numero_residencia or 'S/N'),
                        'complemento': None, 'ativo': True,
                        'id_cidade': cidade_obj.get('id_cidade'),
                        'bairro': (ns.bairro or '').upper(), 'referencia': None,
                        'endereco': ns.rua.upper(),
                        'cep': ''.join(c for c in ns.cep if c.isdigit()),
                        'atualizar_coords_auto': True, 'id_condominio': None,
                        'cidade': cidade_obj,
                    }
            if end is None:                    # fallback: endereço cadastral
                cl = cli.get_cliente(dados.id_cliente_hubsoft)
                enderecos = cl.get('enderecos') or []
                end_cad = next((e for e in enderecos
                                if (e.get('pivot') or {}).get('tipo') == 'cadastral'),
                               enderecos[0] if enderecos else {})
                id_endereco_numero = end_cad.get('id_endereco_numero')
                end = end_cad.get('endereco_numero') or end_cad

            etapa = 'resolver_plano'
            id_servico = int(ns.id_plano_rp)
            plano = cli.buscar_plano_por_id(id_servico)
            valor = float(ns.valor) if ns.valor else float(plano.get('valor') or 0)
            id_vencimento, _dia = cli.resolver_id_vencimento(int(dados.dia_vencimento or 10))

            etapa = 'montar_payload'
            payload = cli.montar_payload_adicionar_servico(
                id_cliente=dados.id_cliente_hubsoft,
                id_endereco_numero=id_endereco_numero, endereco_numero_obj=end,
                id_servico=id_servico, valor=valor, id_vencimento=id_vencimento,
            )

            resumo = {
                'id_cliente': dados.id_cliente_hubsoft, 'id_servico': id_servico,
                'valor': valor, 'id_vencimento': id_vencimento,
                'id_endereco_numero': id_endereco_numero,
                'payload_chaves': sorted(payload.keys()),
            }

            if dry:
                return ResultadoExecucao(
                    status='dry_run', executor=self.nome, etapa='payload_montado',
                    metadados=resumo, duracao_ms=int((time.time() - t0) * 1000))

            etapa = 'adicionar_servico'
            resp = cli.adicionar_servico(payload)
            cs = (resp.get('cliente_servico') or {})
            id_cs = cs.get('id_cliente_servico')
            # NÃO habilitar: igual ao webdriver de produção, o serviço novo fica
            # "Aguardando Instalação" até a OS de instalação ser concluída.
            resumo['id_cliente_servico'] = id_cs
            return ResultadoExecucao(status='sucesso', executor=self.nome, etapa='fim',
                                     metadados=resumo, duracao_ms=int((time.time() - t0) * 1000))
        except Exception as e:  # noqa: BLE001
            return ResultadoExecucao(status='falha', executor=self.nome, etapa=etapa,
                                     erro=f'{type(e).__name__}: {e}'[:500],
                                     duracao_ms=int((time.time() - t0) * 1000))
        finally:
            if cli is not None:
                cli.close()
