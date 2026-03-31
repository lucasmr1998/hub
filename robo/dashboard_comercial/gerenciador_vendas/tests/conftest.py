"""
Fixtures globais para todos os testes.
"""
import pytest
from django.db import connection
from apps.sistema.middleware import set_current_tenant
from tests.factories import TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory


@pytest.fixture(autouse=True, scope='session')
def add_telefone_column(django_db_setup, django_db_blocker):
    """Adiciona coluna telefone ao auth_user (monkey-patch não gera migration)."""
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            try:
                cursor.execute('ALTER TABLE auth_user ADD COLUMN telefone varchar(20)')
            except Exception:
                pass  # Já existe


@pytest.fixture
def tenant_a(db):
    """Tenant A (Provedor Alpha)."""
    return TenantFactory(nome='Provedor Alpha', slug='alpha', plano_comercial='pro')


@pytest.fixture
def tenant_b(db):
    """Tenant B (Provedor Beta)."""
    return TenantFactory(nome='Provedor Beta', slug='beta', plano_comercial='start')


@pytest.fixture
def user_a(db, tenant_a):
    """User do Tenant A."""
    perfil = PerfilFactory(tenant=tenant_a)
    return perfil.user


@pytest.fixture
def user_b(db, tenant_b):
    """User do Tenant B."""
    perfil = PerfilFactory(tenant=tenant_b)
    return perfil.user


@pytest.fixture
def config_a(db, tenant_a):
    """Configuração de empresa do Tenant A."""
    return ConfigEmpresaFactory(tenant=tenant_a)


@pytest.fixture
def config_b(db, tenant_b):
    """Configuração de empresa do Tenant B."""
    return ConfigEmpresaFactory(tenant=tenant_b)


@pytest.fixture
def set_tenant():
    """Fixture para definir/limpar tenant no thread-local."""
    def _set(tenant):
        set_current_tenant(tenant)
    yield _set
    set_current_tenant(None)
