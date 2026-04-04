"""
Testes de integração para views do CS (Customer Success).
Cobre: clube dashboard, parceiros, indicações, suporte.
"""
import pytest
from django.urls import reverse

from apps.sistema.middleware import set_current_tenant
from apps.cs.clube.models import MembroClube, NivelClube
from apps.cs.parceiros.models import CategoriaParceiro, Parceiro
from apps.cs.indicacoes.models import Indicacao
from apps.suporte.models import CategoriaTicket, Ticket
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    MembroClubeFactory, NivelClubeFactory, CategoriaParceiroFactory,
    ParceiroFactory, IndicacaoFactory,
)


@pytest.fixture
def cs_setup(db):
    """Setup CS: tenant com modulo_cs, user, membros, parceiros."""
    tenant = TenantFactory(plano_comercial='pro', modulo_cs=True, plano_cs='start')
    user = UserFactory(is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)

    NivelClubeFactory(tenant=tenant, nome='Bronze', xp_necessario=0)
    NivelClubeFactory(tenant=tenant, nome='Prata', xp_necessario=500)

    membros = [MembroClubeFactory(tenant=tenant) for _ in range(3)]

    cat = CategoriaParceiroFactory(tenant=tenant)
    parceiro = ParceiroFactory(tenant=tenant, categoria=cat)

    return {'tenant': tenant, 'user': user, 'membros': membros, 'parceiro': parceiro}


@pytest.fixture
def logged_cs_client(client, cs_setup):
    client.force_login(cs_setup['user'])
    return client


# ── Clube Dashboard ───────────────────────────────────────────────────────

class TestClubeDashboardViews:
    def test_dashboard_home(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('clube:dashboard_home'))
        assert resp.status_code == 200

    def test_dashboard_participantes(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('clube:dashboard_participantes'))
        assert resp.status_code == 200

    def test_dashboard_premios(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('clube:dashboard_premios'))
        assert resp.status_code == 200

    def test_dashboard_gamificacao(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('clube:dashboard_gamificacao'))
        assert resp.status_code == 200

    def test_dashboard_banners(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('clube:dashboard_banners'))
        assert resp.status_code == 200


# ── Parceiros Dashboard ──────────────────────────────────────────────────

class TestParceirosDashboardViews:
    def test_parceiros_home(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('parceiros:dashboard_parceiros_home'))
        assert resp.status_code == 200

    def test_parceiros_lista(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('parceiros:dashboard_parceiros'))
        assert resp.status_code == 200

    def test_cupons_lista(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('parceiros:dashboard_cupons'))
        assert resp.status_code == 200


# ── Indicações Dashboard ─────────────────────────────────────────────────

class TestIndicacoesDashboardViews:
    def test_indicacoes_home(self, logged_cs_client, cs_setup):
        IndicacaoFactory(tenant=cs_setup['tenant'], membro_indicador=cs_setup['membros'][0])
        resp = logged_cs_client.get(reverse('indicacoes:dashboard_indicacoes_home'))
        assert resp.status_code == 200


# ── Suporte ───────────────────────────────────────────────────────────────

class TestSuporteViews:
    def test_suporte_dashboard(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('suporte:dashboard'))
        assert resp.status_code == 200

    def test_ticket_lista(self, logged_cs_client, cs_setup):
        resp = logged_cs_client.get(reverse('suporte:ticket_lista'))
        assert resp.status_code == 200

    def test_ticket_criar_get(self, logged_cs_client, cs_setup):
        CategoriaTicket.all_tenants.create(
            tenant=cs_setup['tenant'], nome='Bug', slug='bug',
        )
        resp = logged_cs_client.get(reverse('suporte:ticket_criar'))
        assert resp.status_code == 200


# ── Auth ──────────────────────────────────────────────────────────────────

class TestCSAuthRequired:
    @pytest.mark.parametrize('url_name', [
        'clube:dashboard_home', 'clube:dashboard_participantes',
        'parceiros:dashboard_parceiros_home', 'parceiros:dashboard_cupons',
        'suporte:dashboard', 'suporte:ticket_lista',
    ])
    def test_redirect_without_login(self, client, url_name, cs_setup):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
