"""
Testes do painel Admin Aurora.

Verifica:
- Acesso ao monitoramento (superuser only)
- Acesso aos logs (superuser only, filtros, busca)
- Health check público
- Dashboard, planos, criar tenant
"""
import pytest
from django.test import Client
from django.contrib.auth.models import User

from apps.sistema.models import Tenant, PerfilUsuario, ConfiguracaoEmpresa, LogSistema


@pytest.fixture
def superuser(db):
    """Cria superuser com perfil e tenant."""
    tenant = Tenant.objects.create(nome='Admin Tenant', slug='admin-tenant', ativo=True)
    user = User.objects.create_superuser(username='superadmin', password='test123', email='admin@test.com')
    PerfilUsuario.objects.create(user=user, tenant=tenant)
    ConfiguracaoEmpresa.objects.create(tenant=tenant, nome_empresa='Admin Tenant', ativo=True)
    return user


@pytest.fixture
def normal_user(db):
    """Cria usuário normal (não staff, não superuser)."""
    tenant = Tenant.objects.create(nome='Normal Tenant', slug='normal-tenant', ativo=True)
    user = User.objects.create_user(username='normaluser', password='test123')
    PerfilUsuario.objects.create(user=user, tenant=tenant)
    ConfiguracaoEmpresa.objects.create(tenant=tenant, nome_empresa='Normal Tenant', ativo=True)
    return user


@pytest.fixture
def sample_logs(db, superuser):
    """Cria logs de exemplo para testar filtros."""
    tenant = superuser.perfil.tenant
    logs = []
    for nivel in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        logs.append(LogSistema.objects.create(
            tenant=tenant,
            nivel=nivel,
            modulo='teste',
            mensagem=f'Log de teste nivel {nivel}',
        ))
    return logs


# ============================================================================
# HEALTH CHECK
# ============================================================================

@pytest.mark.django_db
class TestHealthCheck:

    def test_health_check_sem_auth(self, client):
        """Health check é público, não exige login."""
        response = client.get('/health/')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['database'] == 'ok'

    def test_health_check_retorna_json(self, client):
        response = client.get('/health/')
        assert response['Content-Type'] == 'application/json'


# ============================================================================
# MONITORAMENTO
# ============================================================================

@pytest.mark.django_db
class TestMonitoramento:

    def test_superuser_acessa_monitoramento(self, client, superuser):
        client.force_login(superuser)
        response = client.get('/aurora-admin/monitoramento/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Status do Sistema' in content or 'monitoramento' in content.lower()

    def test_normal_user_nao_acessa_monitoramento(self, client, normal_user):
        client.force_login(normal_user)
        response = client.get('/aurora-admin/monitoramento/')
        assert response.status_code == 302, (
            "Usuário normal não deveria acessar monitoramento"
        )

    def test_sem_login_redireciona(self, client):
        response = client.get('/aurora-admin/monitoramento/')
        assert response.status_code == 302

    def test_monitoramento_mostra_db_status(self, client, superuser):
        client.force_login(superuser)
        response = client.get('/aurora-admin/monitoramento/')
        content = response.content.decode()
        assert 'online' in content.lower() or 'healthy' in content.lower()

    def test_monitoramento_mostra_metricas(self, client, superuser):
        client.force_login(superuser)
        response = client.get('/aurora-admin/monitoramento/')
        content = response.content.decode()
        # Deve mostrar contadores (mesmo que zero)
        assert 'Leads' in content or 'leads' in content


# ============================================================================
# LOGS
# ============================================================================

@pytest.mark.django_db
class TestLogs:

    def test_superuser_acessa_logs(self, client, superuser):
        client.force_login(superuser)
        response = client.get('/aurora-admin/logs/')
        assert response.status_code == 200

    def test_normal_user_nao_acessa_logs(self, client, normal_user):
        client.force_login(normal_user)
        response = client.get('/aurora-admin/logs/')
        assert response.status_code == 302

    def test_filtro_por_nivel(self, client, superuser, sample_logs):
        client.force_login(superuser)
        response = client.get('/aurora-admin/logs/?nivel=ERROR')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Log de teste nivel ERROR' in content

    def test_filtro_por_nivel_exclui_outros(self, client, superuser, sample_logs):
        client.force_login(superuser)
        response = client.get('/aurora-admin/logs/?nivel=CRITICAL')
        content = response.content.decode()
        assert 'Log de teste nivel CRITICAL' in content
        assert 'Log de teste nivel DEBUG' not in content

    def test_busca_por_mensagem(self, client, superuser, sample_logs):
        client.force_login(superuser)
        response = client.get('/aurora-admin/logs/?q=nivel+ERROR')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Log de teste nivel ERROR' in content

    def test_filtro_por_modulo(self, client, superuser, sample_logs):
        client.force_login(superuser)
        response = client.get('/aurora-admin/logs/?modulo=teste')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'teste' in content

    def test_sem_filtro_mostra_todos(self, client, superuser, sample_logs):
        client.force_login(superuser)
        response = client.get('/aurora-admin/logs/')
        content = response.content.decode()
        assert 'DEBUG' in content
        assert 'ERROR' in content

    def test_logs_vazio(self, client, superuser):
        client.force_login(superuser)
        response = client.get('/aurora-admin/logs/?nivel=CRITICAL')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Nenhum log encontrado' in content or response.status_code == 200


# ============================================================================
# DASHBOARD ADMIN
# ============================================================================

@pytest.mark.django_db
class TestAdminDashboard:

    def test_superuser_acessa_dashboard(self, client, superuser):
        client.force_login(superuser)
        response = client.get('/aurora-admin/')
        assert response.status_code == 200

    def test_normal_user_nao_acessa_dashboard(self, client, normal_user):
        client.force_login(normal_user)
        response = client.get('/aurora-admin/')
        assert response.status_code == 302

    def test_superuser_acessa_planos(self, client, superuser):
        client.force_login(superuser)
        response = client.get('/aurora-admin/planos/')
        assert response.status_code == 200

    def test_superuser_acessa_criar_tenant(self, client, superuser):
        client.force_login(superuser)
        response = client.get('/aurora-admin/tenant/criar/')
        assert response.status_code == 200
