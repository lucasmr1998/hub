"""
Testes de integração para views de Leads e Dashboard.
"""
import pytest
from django.urls import reverse

from apps.sistema.middleware import set_current_tenant
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory, HistoricoContatoFactory,
)


@pytest.fixture
def leads_setup(db):
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    user = UserFactory(is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)

    leads = []
    for i in range(3):
        lead = LeadProspectoFactory.build(
            tenant=tenant, nome_razaosocial=f'Lead View {i}',
            score_qualificacao=i + 3, origem='whatsapp',
        )
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead.save()
        leads.append(lead)
        HistoricoContatoFactory(tenant=tenant, lead=lead)

    return {'tenant': tenant, 'user': user, 'leads': leads}


@pytest.fixture
def logged_leads_client(client, leads_setup):
    client.force_login(leads_setup['user'])
    return client


# ── Leads ─────────────────────────────────────────────────────────────────

class TestLeadsViews:
    def test_leads_page_loads(self, logged_leads_client):
        resp = logged_leads_client.get(reverse('comercial_leads:leads'))
        assert resp.status_code == 200

    def test_sem_login_redireciona(self, client, leads_setup):
        resp = client.get(reverse('comercial_leads:leads'))
        assert resp.status_code == 302


# ── Dashboard ─────────────────────────────────────────────────────────────

class TestDashboardViews:
    def test_dashboard_principal(self, logged_leads_client):
        resp = logged_leads_client.get(reverse('dashboard:dashboard1'))
        assert resp.status_code == 200

    def test_vendas_page(self, logged_leads_client):
        resp = logged_leads_client.get(reverse('dashboard:vendas'))
        assert resp.status_code == 200


# ── Relatórios ────────────────────────────────────────────────────────────

class TestRelatorioViews:
    def test_relatorio_leads(self, logged_leads_client):
        resp = logged_leads_client.get(reverse('dashboard:relatorio_leads'))
        assert resp.status_code == 200

    def test_relatorio_atendimentos(self, logged_leads_client):
        resp = logged_leads_client.get(reverse('dashboard:relatorio_atendimentos'))
        assert resp.status_code == 200


# ── Auth ──────────────────────────────────────────────────────────────────

class TestDashboardAuthRequired:
    @pytest.mark.parametrize('url_name', [
        'dashboard:dashboard1', 'dashboard:vendas',
        'dashboard:relatorio_leads', 'dashboard:relatorio_atendimentos',
    ])
    def test_redirect_without_login(self, client, url_name, db):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
