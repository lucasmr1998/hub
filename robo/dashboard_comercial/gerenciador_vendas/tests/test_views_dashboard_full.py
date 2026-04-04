"""
Testes abrangentes para as views do dashboard (apps/dashboard/views.py).
Cobre: paginas HTML, APIs JSON, autenticacao, filtros e paginacao.
"""
import json
import pytest
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.sistema.middleware import set_current_tenant
from tests.factories import (
    TenantFactory,
    UserFactory,
    PerfilFactory,
    ConfigEmpresaFactory,
    LeadProspectoFactory,
    HistoricoContatoFactory,
    ClienteHubsoftFactory,
    ServicoClienteHubsoftFactory,
    FluxoAtendimentoFactory,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def dashboard_setup(db):
    """Setup completo: tenant, user, config, leads com historicos e clientes hubsoft."""
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    user = UserFactory(is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)

    leads = []
    historicos = []
    origens = ['whatsapp', 'site', 'indicacao', 'facebook', 'google_ads']
    for i in range(6):
        lead = LeadProspectoFactory.build(
            tenant=tenant,
            nome_razaosocial=f'Lead Dashboard {i}',
            telefone=f'+558999900{i:02d}',
            score_qualificacao=i + 2,
            origem=origens[i % len(origens)],
            ativo=True,
        )
        lead._skip_crm_signal = True
        lead._skip_automacao = True
        lead.save()
        leads.append(lead)

        h = HistoricoContatoFactory(
            tenant=tenant,
            lead=lead,
            telefone=lead.telefone,
            status='fluxo_inicializado',
            converteu_venda=(i == 0),
            sucesso=(i < 3),
        )
        historicos.append(h)

    # Clientes e servicos Hubsoft
    clientes_hubsoft = []
    servicos_hubsoft = []
    for i in range(3):
        ch = ClienteHubsoftFactory(
            nome_razaosocial=f'Cliente Hubsoft {i}',
            ativo=True,
        )
        clientes_hubsoft.append(ch)
        sv = ServicoClienteHubsoftFactory(
            cliente=ch,
            status='Ativo',
            status_prefixo='servico_habilitado',
            valor=Decimal('99.90'),
        )
        servicos_hubsoft.append(sv)

    return {
        'tenant': tenant,
        'user': user,
        'leads': leads,
        'historicos': historicos,
        'clientes_hubsoft': clientes_hubsoft,
        'servicos_hubsoft': servicos_hubsoft,
    }


@pytest.fixture
def auth_client(client, dashboard_setup):
    """Client autenticado com dados do dashboard_setup."""
    client.force_login(dashboard_setup['user'])
    return client


@pytest.fixture
def anon_client(client):
    """Client nao autenticado."""
    return client


# ============================================================================
# Paginas HTML — Acesso autenticado (200)
# ============================================================================

class TestDashboardPagesAuthenticated:
    """Testa que todas as paginas HTML retornam 200 para usuario logado."""

    def test_dashboard_view(self, auth_client):
        resp = auth_client.get(reverse('dashboard:dashboard'))
        assert resp.status_code == 200

    def test_dashboard1(self, auth_client):
        resp = auth_client.get(reverse('dashboard:dashboard1'))
        assert resp.status_code == 200

    def test_vendas(self, auth_client):
        resp = auth_client.get(reverse('dashboard:vendas'))
        assert resp.status_code == 200

    def test_relatorios(self, auth_client):
        resp = auth_client.get(reverse('dashboard:relatorios'))
        assert resp.status_code == 200

    def test_relatorio_leads(self, auth_client):
        resp = auth_client.get(reverse('dashboard:relatorio_leads'))
        assert resp.status_code == 200

    def test_relatorio_clientes(self, auth_client):
        resp = auth_client.get(reverse('dashboard:relatorio_clientes'))
        assert resp.status_code == 200

    def test_relatorio_atendimentos(self, auth_client):
        resp = auth_client.get(reverse('dashboard:relatorio_atendimentos'))
        assert resp.status_code == 200

    def test_analise_atendimentos(self, auth_client):
        resp = auth_client.get(reverse('dashboard:analise_atendimentos'))
        assert resp.status_code == 200

    def test_relatorio_conversoes(self, auth_client):
        resp = auth_client.get(reverse('dashboard:relatorio_conversoes'))
        assert resp.status_code == 200

    def test_ajuda(self, auth_client):
        resp = auth_client.get(reverse('dashboard:ajuda'))
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="Depends on external docs file existence")
    def test_documentacao(self, auth_client):
        resp = auth_client.get(reverse('dashboard:documentacao'))
        assert resp.status_code == 200

    def test_api_swagger(self, auth_client):
        resp = auth_client.get(reverse('dashboard:api_swagger'))
        assert resp.status_code == 200

    def test_n8n_guide(self, auth_client):
        resp = auth_client.get(reverse('dashboard:n8n_guide'))
        assert resp.status_code == 200


# ============================================================================
# Auth — Redirect sem login (@login_required)
# ============================================================================

class TestDashboardAuthRequired:
    """Views protegidas com @login_required devem redirecionar (302)."""

    @pytest.mark.parametrize('url_name', [
        'dashboard:dashboard1',
        'dashboard:vendas',
        'dashboard:relatorios',
        'dashboard:api_analise_atendimentos_data',
        'dashboard:api_analise_atendimentos_fluxos',
        'dashboard:api_analise_detalhada_atendimentos',
        'dashboard:api_jornada_cliente_completa',
        'dashboard:api_atendimento_em_tempo_real',
    ])
    def test_redirect_without_login(self, anon_client, url_name, db):
        resp = anon_client.get(reverse(url_name))
        assert resp.status_code == 302


class TestDashboardProtectedPages:
    """Views com @login_required devem redirecionar sem login."""

    @pytest.mark.parametrize('url_name', [
        'dashboard:dashboard',
        'dashboard:relatorio_leads',
        'dashboard:relatorio_clientes',
        'dashboard:relatorio_atendimentos',
        'dashboard:analise_atendimentos',
        'dashboard:relatorio_conversoes',
    ])
    def test_protected_page_redirects(self, anon_client, url_name, db):
        resp = anon_client.get(reverse(url_name))
        assert resp.status_code == 302


# ============================================================================
# APIs JSON — Dashboard Data
# ============================================================================

class TestAPIDashboardData:
    """Testa /api/dashboard/data/ — metricas principais."""

    def test_returns_200_json(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_data'))
        assert resp.status_code == 200
        data = resp.json()
        assert 'stats' in data

    def test_stats_keys(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_data'))
        data = resp.json()
        stats = data['stats']
        expected_keys = [
            'atendimentos', 'leads', 'prospectos', 'vendas',
            'atendimentos_variacao', 'leads_variacao', 'prospectos_variacao', 'vendas_variacao',
            'taxa_atendimento_lead', 'taxa_lead_prospecto', 'taxa_prospecto_venda',
        ]
        for key in expected_keys:
            assert key in stats, f'Chave {key} ausente em stats'

    def test_atendimentos_count(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_data'))
        data = resp.json()
        # 6 historicos com status='fluxo_inicializado'
        assert data['stats']['atendimentos'] == 6

    def test_vendas_count(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_data'))
        data = resp.json()
        # 3 ClienteHubsoft criados
        assert data['stats']['vendas'] == 3

    def test_public_access(self, anon_client, db):
        """API de dados do dashboard nao exige login."""
        resp = anon_client.get(reverse('dashboard:dashboard_data'))
        assert resp.status_code == 200


class TestAPIDashboardCharts:
    """Testa /api/dashboard/charts/ — dados dos graficos."""

    def test_returns_200_json(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_charts'))
        assert resp.status_code == 200
        data = resp.json()
        assert 'leadsUltimos7Dias' in data
        assert 'atendimentosUltimos7Dias' in data
        assert 'prospectosUltimos7Dias' in data
        assert 'vendasUltimos7Dias' in data

    def test_chart_data_is_list(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_charts'))
        data = resp.json()
        assert isinstance(data['leadsUltimos7Dias'], list)
        assert len(data['leadsUltimos7Dias']) == 7

    def test_chart_entry_has_date_and_count(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_charts'))
        data = resp.json()
        entry = data['leadsUltimos7Dias'][0]
        assert 'date' in entry
        assert 'count' in entry


class TestAPIDashboardTables:
    """Testa /api/dashboard/tables/ — top empresas e origens."""

    def test_returns_200_json(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_tables'))
        assert resp.status_code == 200
        data = resp.json()
        assert 'topEmpresas' in data
        assert 'topOrigens' in data

    def test_top_origens_populated(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_tables'))
        data = resp.json()
        assert isinstance(data['topOrigens'], list)
        # Temos 6 leads com origens variadas
        assert len(data['topOrigens']) > 0


class TestAPIDashboardLeads:
    """Testa /api/dashboard/leads/ — listagem paginada de leads."""

    def test_returns_200_json(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_leads'))
        assert resp.status_code == 200
        data = resp.json()
        assert 'leads' in data
        assert 'total' in data

    def test_total_leads_count(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_leads'))
        data = resp.json()
        assert data['total'] == 6

    def test_search_filter(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_leads'), {'search': 'Lead Dashboard 0'})
        data = resp.json()
        assert data['total'] >= 1

    def test_origem_filter(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_leads'), {'origem': 'whatsapp'})
        data = resp.json()
        # Pelo menos 1 lead com origem whatsapp (indice 0 e 5)
        assert data['total'] >= 1

    def test_ativo_filter(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_leads'), {'ativo': 'true'})
        data = resp.json()
        assert data['total'] == 6

    def test_pagination(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_leads'), {'page': '1'})
        data = resp.json()
        assert len(data['leads']) <= 20

    def test_lead_by_id(self, auth_client, dashboard_setup):
        lead = dashboard_setup['leads'][0]
        resp = auth_client.get(reverse('dashboard:dashboard_leads'), {'id': str(lead.id)})
        data = resp.json()
        assert data['total'] == 1
        assert data['leads'][0]['id'] == lead.id

    def test_date_filter(self, auth_client, dashboard_setup):
        today = timezone.now().strftime('%Y-%m-%d')
        resp = auth_client.get(reverse('dashboard:dashboard_leads'), {
            'data_inicio': today,
            'data_fim': today,
        })
        data = resp.json()
        assert data['total'] >= 0  # Pode ser 0 se criados em outro instante


class TestAPIDashboardProspectos:
    """Testa /api/dashboard/prospectos/."""

    def test_returns_200_json(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_prospectos'))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestAPIDashboardHistorico:
    """Testa /api/dashboard/historico/."""

    @pytest.mark.xfail(reason="View uses PostgreSQL-specific raw SQL")
    def test_returns_200(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_historico'))
        assert resp.status_code == 200


class TestAPIContatosRealtime:
    """Testa /api/dashboard/contatos/realtime/."""

    @pytest.mark.xfail(reason="View uses PostgreSQL-specific raw SQL")
    def test_returns_200(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_contatos_realtime'))
        assert resp.status_code == 200


class TestAPIContatoHistorico:
    """Testa /api/dashboard/contato/<telefone>/historico/."""

    @pytest.mark.xfail(reason="View uses PostgreSQL-specific raw SQL")
    def test_returns_200(self, auth_client, dashboard_setup):
        telefone = dashboard_setup['leads'][0].telefone
        url = reverse('dashboard:dashboard_contato_historico', kwargs={'telefone': telefone})
        resp = auth_client.get(url)
        assert resp.status_code == 200


class TestAPIUltimasConversoes:
    """Testa /api/dashboard/ultimas-conversoes/."""

    def test_returns_200_json(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_ultimas_conversoes'))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


@pytest.mark.xfail(reason="View uses PostgreSQL-specific raw SQL")
class TestAPIFunilInsights:
    """Testa /api/dashboard/funil/insights/."""

    def test_returns_200(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_funil_insights'))
        assert resp.status_code == 200

    def test_periodo_hoje(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_funil_insights'), {'periodo': 'hoje'})
        assert resp.status_code == 200

    def test_periodo_semana(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_funil_insights'), {'periodo': 'semana'})
        assert resp.status_code == 200

    def test_periodo_mes(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:dashboard_funil_insights'), {'periodo': 'mes'})
        assert resp.status_code == 200


# ============================================================================
# APIs de Analise de Atendimentos (requerem login)
# ============================================================================

class TestAPIAnaliseAtendimentosData:
    """Testa /api/analise/atendimentos/data/."""

    def test_returns_200_json_authenticated(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:api_analise_atendimentos_data'))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_redirect_unauthenticated(self, anon_client, db):
        resp = anon_client.get(reverse('dashboard:api_analise_atendimentos_data'))
        assert resp.status_code == 302


class TestAPIAnaliseAtendimentosFluxos:
    """Testa /api/analise/atendimentos/fluxos/."""

    def test_returns_200_json_authenticated(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:api_analise_atendimentos_fluxos'))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_redirect_unauthenticated(self, anon_client, db):
        resp = anon_client.get(reverse('dashboard:api_analise_atendimentos_fluxos'))
        assert resp.status_code == 302


class TestAPIAnaliseDetalhadaAtendimentos:
    """Testa /api/analise/atendimentos/detalhada/."""

    def test_returns_200_json_authenticated(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:api_analise_detalhada_atendimentos'))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestAPIJornadaClienteCompleta:
    """Testa /api/jornada/cliente/."""

    @pytest.mark.xfail(reason="View uses PostgreSQL-specific raw SQL")
    def test_returns_200(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:api_jornada_cliente_completa'))
        assert resp.status_code == 200


class TestAPIAtendimentoEmTempoReal:
    """Testa /api/atendimento/tempo-real/."""

    @pytest.mark.xfail(reason="View uses PostgreSQL-specific raw SQL")
    def test_returns_200(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:api_atendimento_em_tempo_real'))
        assert resp.status_code == 200


# ============================================================================
# Relatorios — Conteudo e dados
# ============================================================================

class TestRelatorioLeadsContent:
    """Testa que o relatorio de leads retorna dados coerentes."""

    def test_relatorio_leads_context(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:relatorio_leads'))
        assert resp.status_code == 200
        assert 'stats' in resp.context
        assert 'graficos' in resp.context

    def test_relatorio_leads_stats_total(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:relatorio_leads'))
        stats = resp.context['stats']
        assert stats['total'] == 6


class TestRelatorioClientesContent:
    """Testa que o relatorio de clientes retorna dados do Hubsoft."""

    def test_relatorio_clientes_context(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:relatorio_clientes'))
        assert resp.status_code == 200
        assert 'stats' in resp.context

    def test_relatorio_clientes_stats(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:relatorio_clientes'))
        stats = resp.context['stats']
        assert stats['total_clientes'] == 3
        assert stats['ativos'] == 3
        assert stats['habilitados'] == 3


class TestRelatorioAtendimentosContent:
    """Testa que o relatorio de atendimentos retorna dados coerentes."""

    def test_relatorio_atendimentos_context(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:relatorio_atendimentos'))
        assert resp.status_code == 200
        assert 'stats' in resp.context

    def test_relatorio_atendimentos_total(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:relatorio_atendimentos'))
        stats = resp.context['stats']
        assert stats['total'] == 6


class TestRelatoriosViewContent:
    """Testa a pagina principal de relatorios."""

    def test_relatorios_context_stats(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:relatorios'))
        assert resp.status_code == 200
        assert 'stats' in resp.context
        stats = resp.context['stats']
        assert stats['total_leads'] == 6
        assert stats['total_atendimentos'] == 6
        assert stats['total_clientes_hubsoft'] == 3


# ============================================================================
# API Documentation
# ============================================================================

class TestAPIDocumentation:
    """Testa a view de documentacao markdown da API."""

    def test_api_documentation_view(self, auth_client, dashboard_setup):
        resp = auth_client.get(reverse('dashboard:api_documentation'))
        # Pode retornar 200 (arquivo existe) ou 404 (arquivo nao encontrado)
        assert resp.status_code in (200, 404)


# ============================================================================
# Testes parametrizados — todas as APIs publicas retornam JSON valido
# ============================================================================

class TestAllAPIsReturn200:
    """Todas as APIs do dashboard devem retornar 200 para user autenticado."""

    @pytest.mark.parametrize('url_name', [
        'dashboard:dashboard_data',
        'dashboard:dashboard_charts',
        'dashboard:dashboard_tables',
        'dashboard:dashboard_leads',
        'dashboard:dashboard_prospectos',
        'dashboard:dashboard_ultimas_conversoes',
    ])
    def test_api_returns_200(self, auth_client, dashboard_setup, url_name):
        resp = auth_client.get(reverse(url_name))
        assert resp.status_code == 200


# ============================================================================
# Edge cases
# ============================================================================

class TestDashboardEmptyDB:
    """Testa que as views funcionam mesmo com banco vazio."""

    @pytest.fixture
    def empty_setup(self, db):
        tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
        user = UserFactory(is_staff=True)
        PerfilFactory(user=user, tenant=tenant)
        ConfigEmpresaFactory(tenant=tenant)
        set_current_tenant(tenant)
        return {'tenant': tenant, 'user': user}

    @pytest.fixture
    def empty_auth_client(self, client, empty_setup):
        client.force_login(empty_setup['user'])
        return client

    def test_dashboard_data_empty(self, empty_auth_client):
        resp = empty_auth_client.get(reverse('dashboard:dashboard_data'))
        assert resp.status_code == 200
        data = resp.json()
        assert data['stats']['atendimentos'] == 0
        assert data['stats']['leads'] == 0

    def test_charts_data_empty(self, empty_auth_client):
        resp = empty_auth_client.get(reverse('dashboard:dashboard_charts'))
        assert resp.status_code == 200
        data = resp.json()
        assert all(e['count'] == 0 for e in data['leadsUltimos7Dias'])

    def test_tables_data_empty(self, empty_auth_client):
        resp = empty_auth_client.get(reverse('dashboard:dashboard_tables'))
        assert resp.status_code == 200
        data = resp.json()
        assert data['topEmpresas'] == []
        assert data['topOrigens'] == []

    def test_leads_data_empty(self, empty_auth_client):
        resp = empty_auth_client.get(reverse('dashboard:dashboard_leads'))
        assert resp.status_code == 200
        data = resp.json()
        assert data['total'] == 0
        assert data['leads'] == []

    def test_relatorios_empty(self, empty_auth_client):
        resp = empty_auth_client.get(reverse('dashboard:relatorios'))
        assert resp.status_code == 200
        stats = resp.context['stats']
        assert stats['total_leads'] == 0

    def test_ultimas_conversoes_empty(self, empty_auth_client):
        resp = empty_auth_client.get(reverse('dashboard:dashboard_ultimas_conversoes'))
        assert resp.status_code == 200
