"""Testes do adaptador robo_matrix: resolucao de tenant pelo token na URL.

PRIORIDADE 1 (isolamento): o token na URL (/robo/<token>/ia/...) tem que
resolver exatamente a empresa dona do api_token, e nunca vazar entre tenants.
"""
import pytest
from django.test import Client

from apps.integracoes.models import IntegracaoAPI


def _integracao_token(tenant, token):
    """Cria uma IntegracaoAPI ativa cujo api_token identifica o tenant."""
    return IntegracaoAPI.all_tenants.create(
        tenant=tenant,
        api_token=token,
        nome=f'Robo Matrix {tenant.slug}',
        tipo='n8n',
        ativa=True,
        client_id='',
        client_secret='',
        username='',
        password='',
    )


class TestResolucaoTenantPorToken:
    def test_token_resolve_tenant_certo(self, db, tenant_a, tenant_b):
        _integracao_token(tenant_a, 'tok-alpha')
        _integracao_token(tenant_b, 'tok-beta')
        client = Client()

        r_a = client.get('/robo/tok-alpha/ia/ping')
        assert r_a.status_code == 200
        assert r_a.json()['tenant_slug'] == 'alpha'

        r_b = client.get('/robo/tok-beta/ia/ping')
        assert r_b.status_code == 200
        assert r_b.json()['tenant_slug'] == 'beta'

    def test_token_invalido_401(self, db, tenant_a):
        _integracao_token(tenant_a, 'tok-alpha')
        r = Client().get('/robo/nao-existe/ia/ping')
        assert r.status_code == 401

    def test_integracao_inativa_nao_resolve(self, db, tenant_a):
        integ = _integracao_token(tenant_a, 'tok-alpha')
        integ.ativa = False
        integ.save(update_fields=['ativa'])
        r = Client().get('/robo/tok-alpha/ia/ping')
        assert r.status_code == 401
