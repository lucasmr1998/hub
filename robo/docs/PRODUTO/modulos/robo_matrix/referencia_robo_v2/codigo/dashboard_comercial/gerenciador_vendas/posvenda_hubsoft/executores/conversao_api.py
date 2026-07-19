"""Executor de CONVERSÃO prospecto→cliente via API interna do HubSoft.

Substitui o webdriver de produção (gestao_leads_bot / main_refatorado): em vez de
navegar o wizard "Converter em Cliente", faz o MESMO POST /api/v1/cliente que o
wizard faz no SALVAR — com o objeto completo do cliente (identidade + serviço +
endereço + contrato + grupo Varejo) + id_prospecto (linka o prospecto → cliente).

Estrutura descoberta por captura CDP (hubsoft_capturar_conversao →
templates/template_conversao.json). Reaproveita o construtor montar_payload do
cliente_http (já usado na migração). No dry-run monta o payload mas não faz o POST.
"""
from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace

from .base import Executor, ResultadoExecucao, dry_run_efetivo
from ..services.ambiente import preparar_ambiente_webdriver

_TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'api_interna', 'templates', 'template_conversao.json')


def _dados_do_lead(lead) -> SimpleNamespace:
    """Monta o objeto `dados` que montar_payload/resolver_endereço esperam."""
    dn = ''
    if lead.data_nascimento:
        dn = (lead.data_nascimento.strftime('%d/%m/%Y')
              if hasattr(lead.data_nascimento, 'strftime') else str(lead.data_nascimento))
    return SimpleNamespace(
        cpf_cnpj=lead.cpf_cnpj or '',
        nome=lead.nome_razaosocial or '',
        telefone_1=lead.telefone or '',
        email_principal=lead.email or '',
        data_nascimento=dn,
        tipo_cliente='fisica',
        id_plano_megalink=lead.id_plano_rp,
        dia_vencimento=10,                       # dia válido; montar_payload resolve o id
        cep=lead.cep or '', rua=lead.rua or (lead.endereco or ''),
        numero=lead.numero_residencia or 'S/N', bairro=lead.bairro or '',
        complemento=getattr(lead, 'complemento', '') or '',
        referencia=getattr(lead, 'ponto_referencia', '') or '',
    )


class ExecutorApiConversao(Executor):
    nome = 'api_interna'
    processo = 'conversao'

    def __init__(self, *, headless: bool = True, **_):
        self.headless = headless

    def executar(self, registro_id: int, *, dry_run: bool) -> ResultadoExecucao:
        t0 = time.time()
        cli = None
        etapa = 'init'
        try:
            from vendas_web.models import LeadProspecto
            lead = LeadProspecto.objects.get(pk=registro_id)
            if not lead.id_hubsoft:
                return ResultadoExecucao(status='falha', executor=self.nome,
                                         etapa='validar', erro='lead sem id_hubsoft (prospecto)',
                                         duracao_ms=int((time.time() - t0) * 1000))

            dry = dry_run_efetivo(dry_run, lead.cpf_cnpj or '')
            preparar_ambiente_webdriver()
            from ..api_interna.cliente_http import ClienteHTTP
            cli = ClienteHTTP(headless=self.headless)
            etapa = 'login'
            cli.login()

            etapa = 'resolver_endereco'
            dados = _dados_do_lead(lead)
            cep_data = cli.buscar_cep(dados.cep)
            cidade_obj = (cep_data or {}).get('cidade_completo')
            if not cidade_obj:
                return ResultadoExecucao(status='falha', executor=self.nome,
                                         etapa='resolver_endereco',
                                         erro=f'CEP {dados.cep!r} sem cidade',
                                         duracao_ms=int((time.time() - t0) * 1000))
            endereco_resolvido = {
                'id_endereco_numero': None,
                'cep': ''.join(c for c in dados.cep if c.isdigit()),
                'endereco': dados.rua, 'numero': str(dados.numero or 'S/N'),
                'bairro': dados.bairro, 'complemento': dados.complemento or None,
                'referencia': dados.referencia or None, 'cidade': cidade_obj,
                'estado': cidade_obj.get('estado', {}), 'pais': (cep_data or {}).get('pais', {}),
                'condominio': None, 'atualizar_coords_auto': True,
            }

            etapa = 'montar_payload'
            with open(_TEMPLATE, encoding='utf-8') as f:
                template = json.load(f)
            payload = cli.montar_payload(dados, template, endereco_resolvido)
            # ── campos que tornam o POST uma CONVERSÃO (linka o prospecto) ──
            payload['id_prospecto'] = int(lead.id_hubsoft)
            payload['rg'] = lead.rg or ''
            payload['telefone_secundario'] = ''

            resumo = {'id_prospecto': payload['id_prospecto'], 'cpf': dados.cpf_cnpj,
                      'id_servico': dados.id_plano_megalink, 'nome': dados.nome}
            if dry:
                return ResultadoExecucao(status='dry_run', executor=self.nome,
                                         etapa='payload_montado', metadados=resumo,
                                         duracao_ms=int((time.time() - t0) * 1000))

            etapa = 'criar_cliente'
            resp = cli.criar_cliente(payload)
            cli_obj = (resp or {}).get('cliente') or {}
            resumo['id_cliente_novo'] = cli_obj.get('id_cliente') or cli_obj.get('codigo_cliente')
            return ResultadoExecucao(status='sucesso', executor=self.nome, etapa='fim',
                                     metadados=resumo, duracao_ms=int((time.time() - t0) * 1000))
        except Exception as e:  # noqa: BLE001
            return ResultadoExecucao(status='falha', executor=self.nome, etapa=etapa,
                                     erro=f'{type(e).__name__}: {e}'[:500],
                                     duracao_ms=int((time.time() - t0) * 1000))
        finally:
            if cli is not None:
                cli.close()
