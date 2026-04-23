"""
Testes de integração para views de Sistema, Configurações e Admin Aurora.
"""
import pytest
from django.urls import reverse

from apps.sistema.middleware import set_current_tenant
from tests.factories import TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory


@pytest.fixture
def sys_setup(db):
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True, modulo_cs=True)
    user = UserFactory(is_staff=True, is_superuser=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)
    return {'tenant': tenant, 'user': user}


@pytest.fixture
def logged_sys_client(client, sys_setup):
    client.force_login(sys_setup['user'])
    return client


# ── Sistema / Configurações ───────────────────────────────────────────────

class TestSistemaViews:
    def test_configuracoes(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('sistema:configuracoes'))
        assert resp.status_code == 200

    def test_configuracoes_usuarios(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('sistema:configuracoes_usuarios'))
        assert resp.status_code == 200

    def test_login_page(self, client, sys_setup):
        resp = client.get(reverse('sistema:login'))
        assert resp.status_code == 200

    def test_login_post_valido(self, client, sys_setup):
        resp = client.post(reverse('sistema:login'), {
            'email': sys_setup['user'].email,
            'password': 'senha123',
        })
        assert resp.status_code == 302  # Redirect após login

    def test_login_post_invalido(self, client, sys_setup):
        resp = client.post(reverse('sistema:login'), {
            'email': sys_setup['user'].email,
            'password': 'errada',
        })
        assert resp.status_code == 200  # Fica na página de login

    def test_logout(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('sistema:logout'))
        assert resp.status_code == 302


# ── Admin Aurora ──────────────────────────────────────────────────────────

class TestAdminAuroraViews:
    def test_dashboard(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('admin_aurora:dashboard'))
        assert resp.status_code == 200

    def test_criar_tenant_get(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('admin_aurora:criar_tenant'))
        assert resp.status_code == 200

    def test_logs(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('admin_aurora:logs'))
        assert resp.status_code == 200

    def test_monitoramento(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('admin_aurora:monitoramento'))
        assert resp.status_code == 200

    def test_planos(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('admin_aurora:planos'))
        assert resp.status_code == 200

    def test_produto(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('admin_aurora:produto'))
        assert resp.status_code == 200

    def test_docs(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('admin_aurora:docs'))
        assert resp.status_code == 200

    def test_backlog(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('admin_aurora:backlog'))
        assert resp.status_code == 200

    def test_admin_aurora_sem_superuser_nega(self, client, sys_setup):
        normal_user = UserFactory()
        PerfilFactory(user=normal_user, tenant=sys_setup['tenant'])
        client.force_login(normal_user)
        resp = client.get(reverse('admin_aurora:dashboard'))
        assert resp.status_code == 302  # Redireciona para login


# ── Marketing ─────────────────────────────────────────────────────────────

class TestMarketingViews:
    def test_campanhas_trafego(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('marketing_campanhas:campanhas_trafego'))
        assert resp.status_code == 200

    def test_automacoes_lista(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('marketing_automacoes:lista'))
        assert resp.status_code == 200

    def test_automacoes_criar(self, logged_sys_client, sys_setup):
        resp = logged_sys_client.get(reverse('marketing_automacoes:criar'))
        assert resp.status_code == 200
