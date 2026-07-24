"""Webhook N8N nao abre oportunidade se o lead ja e cliente no HubSoft (tarefa 224).

Decisoes do dono:
  - a checagem e no NOSSO webhook (opcao B), por CPF ou telefone
  - 'e cliente' = qualquer cadastro (nao filtra serviço ativo)
  - fail-open: erro na consulta -> cria a oportunidade normalmente
"""
import json
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.comercial.crm.models import OportunidadeVenda, Pipeline, PipelineEstagio
from apps.comercial.leads.models import LeadProspecto
from apps.integracoes import views_n8n_webhook as webhook
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.sistema.middleware import set_current_tenant
from tests.factories import (
    IntegracaoAPIFactory,
    LeadProspectoFactory,
    TenantFactory,
)


class TestTelefoneParaBusca:
    @pytest.mark.parametrize('entrada,esperado', [
        ('5519998142113', '19998142113'),   # 13 dig com 55 -> 11 (o gargalo real)
        ('19998142113', '19998142113'),      # ja 11 -> mantem
        ('551938213500', '1938213500'),      # 12 dig com 55 (fixo) -> 10
        ('(19) 99814-2113', '19998142113'),  # tira mascara
        ('', ''),
        (None, ''),
    ])
    def test_normaliza(self, entrada, esperado):
        svc = HubsoftService.__new__(HubsoftService)   # so o metodo, sem __init__
        assert svc._telefone_para_busca(entrada) == esperado


@pytest.fixture
def svc(db):
    return HubsoftService(IntegracaoAPIFactory())


class TestBuscarClienteQualquer:
    def test_acha_por_cpf_primeiro(self, svc):
        with patch.object(svc, '_get',
                          return_value={'status': 'success', 'clientes': [{'codigo_cliente': 60346}]}) as m:
            c = svc.buscar_cliente_qualquer(cpf_cnpj='282.866.318-38', telefone='5519998142113')
        assert c['codigo_cliente'] == 60346
        assert m.call_args_list[0].kwargs['params']['busca'] == 'cpf_cnpj'

    def test_cai_pro_telefone_quando_sem_cpf(self, svc):
        with patch.object(svc, '_get',
                          return_value={'status': 'success', 'clientes': [{'codigo_cliente': 1}]}) as m:
            c = svc.buscar_cliente_qualquer(cpf_cnpj='', telefone='5519998142113')
        assert c['codigo_cliente'] == 1
        p = m.call_args_list[0].kwargs['params']
        assert p['busca'] == 'telefone'
        assert p['termo_busca'] == '19998142113'      # normalizado, sem o 55

    def test_none_quando_nenhum_bate(self, svc):
        with patch.object(svc, '_get', return_value={'status': 'success', 'clientes': []}):
            assert svc.buscar_cliente_qualquer(cpf_cnpj='11122233344', telefone='5519998142113') is None

    def test_erro_no_cpf_nao_impede_telefone(self, svc):
        def fake(endpoint, params=None, lead=None):
            if params['busca'] == 'cpf_cnpj':
                raise HubsoftServiceError('boom')
            return {'status': 'success', 'clientes': [{'codigo_cliente': 9}]}
        with patch.object(svc, '_get', side_effect=fake):
            c = svc.buscar_cliente_qualquer(cpf_cnpj='123', telefone='5519998142113')
        assert c['codigo_cliente'] == 9


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    set_current_tenant(tenant)
    pipeline = Pipeline.all_tenants.create(
        tenant=tenant, nome='Vendas', slug='vendas', tipo='vendas', padrao=True)
    PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Novo', slug='novo', tipo='novo', ordem=1)
    return tenant


def _post(client, tenant, telefone='5519998142113', nome='Fulano', cpf=''):
    body = {'tenant_slug': tenant.slug, 'telefone': telefone, 'nome_razaosocial': nome}
    if cpf:
        body['cpf'] = cpf
    return client.post(
        reverse('integracoes_n8n_public:n8n_receber_lead'),
        data=json.dumps(body), content_type='application/json')


class TestGateCliente:
    def test_cliente_nao_abre_oportunidade(self, client, cenario):
        t = cenario
        with patch.object(webhook, '_autorizado', return_value=True), \
             patch.object(webhook, '_ja_e_cliente_hubsoft', return_value={'codigo_cliente': 60346}):
            resp = _post(client, t, nome='Rosangela')
        assert resp.status_code == 200
        d = resp.json()
        assert d['eh_cliente'] is True
        assert d['oportunidade_id'] is None
        assert d['codigo_cliente_hubsoft'] == 60346
        lead = LeadProspecto.all_tenants.get(pk=d['lead_id'])
        assert (lead.dados_custom or {}).get('eh_cliente_hubsoft') is True
        assert not OportunidadeVenda.all_tenants.filter(tenant=t, lead=lead).exists()

    def test_nao_cliente_abre_oportunidade(self, client, cenario):
        t = cenario
        with patch.object(webhook, '_autorizado', return_value=True), \
             patch.object(webhook, '_ja_e_cliente_hubsoft', return_value=None):
            resp = _post(client, t, telefone='5511900000000', nome='Novo Lead')
        assert resp.status_code in (200, 201)
        d = resp.json()
        assert d['eh_cliente'] is False
        assert d['oportunidade_id'] is not None
        lead = LeadProspecto.all_tenants.get(pk=d['lead_id'])
        assert OportunidadeVenda.all_tenants.filter(tenant=t, lead=lead).exists()

    def test_fail_open_sem_integracao(self, cenario):
        """Sem IntegracaoAPI hubsoft, a checagem devolve None (nao trava)."""
        t = cenario
        lead = LeadProspectoFactory.build(tenant=t, telefone='5519998142113')
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead.save()
        assert webhook._ja_e_cliente_hubsoft(t, lead) is None

    def test_fail_open_quando_api_erra(self, cenario):
        """API do HubSoft fora -> None, e o webhook segue e cria a oportunidade."""
        t = cenario
        IntegracaoAPIFactory(tenant=t)     # hubsoft ativa
        lead = LeadProspectoFactory.build(tenant=t, telefone='5519998142113')
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead.save()
        with patch.object(HubsoftService, 'buscar_cliente_qualquer', side_effect=RuntimeError('down')):
            assert webhook._ja_e_cliente_hubsoft(t, lead) is None
