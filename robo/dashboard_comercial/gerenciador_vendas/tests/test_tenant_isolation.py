"""
Testes de isolamento multi-tenant.

PRIORIDADE 1: Se qualquer um desses testes falhar, há risco de vazamento
de dados entre provedores.
"""
import pytest
from django.contrib.auth.models import User

from apps.sistema.models import Tenant, PerfilUsuario, ConfiguracaoEmpresa, LogSistema, StatusConfiguravel
from apps.sistema.middleware import set_current_tenant, get_current_tenant
from apps.comercial.leads.models import LeadProspecto, ImagemLeadProspecto, Prospecto, HistoricoContato
from apps.comercial.atendimento.models import FluxoAtendimento
from apps.marketing.campanhas.models import CampanhaTrafego


# ── TenantManager: auto-filtro ───────────────────────────────────────────────

class TestTenantManagerAutoFilter:
    """objects.all() deve retornar APENAS dados do tenant ativo."""

    def test_lead_isolado_por_tenant(self, db, tenant_a, tenant_b, set_tenant):
        LeadProspecto.all_tenants.create(
            nome_razaosocial='Lead Alpha', telefone='+5511900000001', tenant=tenant_a
        )
        LeadProspecto.all_tenants.create(
            nome_razaosocial='Lead Beta', telefone='+5511900000002', tenant=tenant_b
        )

        set_tenant(tenant_a)
        leads_a = list(LeadProspecto.objects.values_list('nome_razaosocial', flat=True))
        assert leads_a == ['Lead Alpha']

        set_tenant(tenant_b)
        leads_b = list(LeadProspecto.objects.values_list('nome_razaosocial', flat=True))
        assert leads_b == ['Lead Beta']

    def test_sem_tenant_ve_tudo(self, db, tenant_a, tenant_b, set_tenant):
        LeadProspecto.all_tenants.create(
            nome_razaosocial='Lead A', telefone='+5511900000003', tenant=tenant_a
        )
        LeadProspecto.all_tenants.create(
            nome_razaosocial='Lead B', telefone='+5511900000004', tenant=tenant_b
        )

        set_tenant(None)
        assert LeadProspecto.objects.count() == 2

    def test_all_tenants_ignora_filtro(self, db, tenant_a, tenant_b, set_tenant):
        LeadProspecto.all_tenants.create(
            nome_razaosocial='Lead A', telefone='+5511900000005', tenant=tenant_a
        )
        LeadProspecto.all_tenants.create(
            nome_razaosocial='Lead B', telefone='+5511900000006', tenant=tenant_b
        )

        set_tenant(tenant_a)
        assert LeadProspecto.all_tenants.count() == 2
        assert LeadProspecto.objects.count() == 1

    def test_fluxo_atendimento_isolado(self, db, tenant_a, tenant_b, set_tenant):
        FluxoAtendimento.all_tenants.create(
            nome='Fluxo Alpha', tenant=tenant_a
        )
        FluxoAtendimento.all_tenants.create(
            nome='Fluxo Beta', tenant=tenant_b
        )

        set_tenant(tenant_a)
        assert FluxoAtendimento.objects.count() == 1
        assert FluxoAtendimento.objects.first().nome == 'Fluxo Alpha'

    def test_config_empresa_isolada(self, db, config_a, config_b, set_tenant):
        set_tenant(config_a.tenant)
        configs = ConfiguracaoEmpresa.objects.all()
        assert configs.count() == 1
        assert configs.first().nome_empresa == config_a.nome_empresa

    def test_log_sistema_isolado(self, db, tenant_a, tenant_b, set_tenant):
        LogSistema.all_tenants.create(
            nivel='ERROR', modulo='teste', mensagem='Erro Alpha', tenant=tenant_a
        )
        LogSistema.all_tenants.create(
            nivel='INFO', modulo='teste', mensagem='Info Beta', tenant=tenant_b
        )

        set_tenant(tenant_a)
        logs = LogSistema.objects.all()
        assert logs.count() == 1
        assert logs.first().mensagem == 'Erro Alpha'


# ── TenantMixin: auto-save ──────────────────────────────────────────────────

class TestTenantMixinAutoSave:
    """save() deve auto-preencher tenant_id quando dentro de um request."""

    def test_auto_preenche_tenant_no_save(self, db, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspecto(nome_razaosocial='Auto Lead', telefone='+5511900000010')
        lead.save()
        assert lead.tenant == tenant_a

    def test_nao_sobrescreve_tenant_existente(self, db, tenant_a, tenant_b, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspecto(
            nome_razaosocial='Lead Fixo', telefone='+5511900000011', tenant=tenant_b
        )
        lead.save()
        assert lead.tenant == tenant_b  # Não sobrescreveu

    def test_sem_tenant_salva_null(self, db, set_tenant):
        set_tenant(None)
        lead = LeadProspecto(nome_razaosocial='Lead Sem Tenant', telefone='+5511900000012')
        lead.save()
        assert lead.tenant is None


# ── Middleware ────────────────────────────────────────────────────────────────

class TestTenantMiddleware:
    """Middleware resolve tenant corretamente a partir do user."""

    def test_user_com_perfil_resolve_tenant(self, db, tenant_a, user_a, client):
        client.force_login(user_a)
        response = client.get('/dashboard/')
        assert response.wsgi_request.tenant == tenant_a

    def test_user_sem_perfil_tenant_none(self, db, client):
        user = User.objects.create_user(username='orphan', password='teste123')
        client.force_login(user)
        response = client.get('/dashboard/')
        assert response.wsgi_request.tenant is None

    def test_anonimo_tenant_none(self, db, client):
        response = client.get('/login/')
        assert response.wsgi_request.tenant is None

    def test_thread_local_limpa_apos_request(self, db, user_a, client):
        client.force_login(user_a)
        client.get('/dashboard/')
        assert get_current_tenant() is None  # Limpo após response


# ── Cross-tenant query protection ────────────────────────────────────────────

class TestCrossTenantProtection:
    """Queries filtradas não devem retornar dados de outro tenant."""

    def test_filter_por_campo_nao_vaza(self, db, tenant_a, tenant_b, set_tenant):
        LeadProspecto.all_tenants.create(
            nome_razaosocial='João Silva', telefone='+5511900000020', tenant=tenant_a
        )
        LeadProspecto.all_tenants.create(
            nome_razaosocial='João Silva', telefone='+5511900000021', tenant=tenant_b
        )

        set_tenant(tenant_a)
        joaos = LeadProspecto.objects.filter(nome_razaosocial='João Silva')
        assert joaos.count() == 1
        assert joaos.first().tenant == tenant_a

    def test_get_por_pk_de_outro_tenant_nao_retorna(self, db, tenant_a, tenant_b, set_tenant):
        lead_b = LeadProspecto.all_tenants.create(
            nome_razaosocial='Lead B', telefone='+5511900000022', tenant=tenant_b
        )

        set_tenant(tenant_a)
        with pytest.raises(LeadProspecto.DoesNotExist):
            LeadProspecto.objects.get(pk=lead_b.pk)

    def test_count_reflete_apenas_tenant_ativo(self, db, tenant_a, tenant_b, set_tenant):
        for i in range(5):
            LeadProspecto.all_tenants.create(
                nome_razaosocial=f'Lead A{i}', telefone=f'+551190000010{i}', tenant=tenant_a
            )
        for i in range(3):
            LeadProspecto.all_tenants.create(
                nome_razaosocial=f'Lead B{i}', telefone=f'+551190000020{i}', tenant=tenant_b
            )

        set_tenant(tenant_a)
        assert LeadProspecto.objects.count() == 5

        set_tenant(tenant_b)
        assert LeadProspecto.objects.count() == 3
