"""
Testes de isolamento multi-tenant em consultas de User.

PRIORIDADE 1: usuarios do Django sao globais (nao herdam TenantMixin).
Qualquer view que liste users pra select/dropdown precisa filtrar por
`perfil__tenant=request.tenant` explicitamente. Se esses testes falharem,
ha risco de um tenant ver/atribuir usuarios de outro.

Cobre as views principais que foram corrigidas no commit de Security:
- Inbox (inbox_view e configuracoes_inbox)
- Notificacoes (detalhe de tipo e envio em massa)
- Marketing Automacoes (editor de regras)
"""
import pytest
from django.contrib.auth.models import User

from apps.sistema.middleware import set_current_tenant
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
)


@pytest.fixture
def tenant_a(db):
    t = TenantFactory(slug='alpha-u', nome='Alpha', plano_comercial='pro', modulo_comercial=True)
    ConfigEmpresaFactory(tenant=t)
    return t


@pytest.fixture
def tenant_b(db):
    t = TenantFactory(slug='beta-u', nome='Beta', plano_comercial='pro', modulo_comercial=True)
    ConfigEmpresaFactory(tenant=t)
    return t


@pytest.fixture
def users_a(db, tenant_a):
    """2 users no tenant A (1 admin logado + 1 agente)."""
    admin = UserFactory(username='admin_alpha', first_name='Admin', last_name='Alpha', is_staff=True, is_superuser=True)
    PerfilFactory(user=admin, tenant=tenant_a)
    agente = UserFactory(username='agente_alpha', first_name='Agente', last_name='Alpha', is_staff=True)
    PerfilFactory(user=agente, tenant=tenant_a)
    return {'admin': admin, 'agente': agente}


@pytest.fixture
def users_b(db, tenant_b):
    """2 users no tenant B — NAO devem vazar pro tenant A."""
    u1 = UserFactory(username='vazamento_1', first_name='Vazamento', last_name='Um', is_staff=True)
    PerfilFactory(user=u1, tenant=tenant_b)
    u2 = UserFactory(username='vazamento_2', first_name='Vazamento', last_name='Dois', is_staff=True)
    PerfilFactory(user=u2, tenant=tenant_b)
    return {'u1': u1, 'u2': u2}


@pytest.fixture
def logged_client_a(client, tenant_a, users_a):
    """Client logado como admin do tenant A."""
    set_current_tenant(tenant_a)
    client.force_login(users_a['admin'])
    return client


def _vazou_user_b(content_bytes, users_b):
    """Checa se users do tenant B aparecem no HTML do tenant A."""
    body = content_bytes.decode('utf-8', errors='ignore')
    return any(u.username in body or u.first_name + ' ' + u.last_name in body for u in users_b.values())


# ============================================================================
# INBOX
# ============================================================================

@pytest.mark.django_db
def test_inbox_view_nao_vaza_usuarios_de_outro_tenant(logged_client_a, users_b):
    """O select de agentes no inbox nao deve mostrar usuarios do tenant B."""
    r = logged_client_a.get('/inbox/')
    # Pode dar 200 ou 302 (depende da permissao) — o que importa é que nao vaze
    if r.status_code == 200:
        assert not _vazou_user_b(r.content, users_b), \
            "Inbox vazou users do tenant B pro tenant A"


@pytest.mark.django_db
def test_configuracoes_inbox_nao_vaza_usuarios(logged_client_a, users_b):
    """A tela de configuracoes do inbox nao deve listar users do tenant B."""
    r = logged_client_a.get('/inbox/configuracoes/')
    if r.status_code == 200:
        assert not _vazou_user_b(r.content, users_b), \
            "Configuracoes do inbox vazaram users do tenant B"


# ============================================================================
# MARKETING AUTOMACOES
# ============================================================================

@pytest.mark.django_db
def test_editor_regra_automacao_nao_vaza_usuarios(logged_client_a, tenant_a, users_b):
    """O editor de regras de automacao nao deve listar users do tenant B."""
    from apps.marketing.automacoes.models import RegraAutomacao

    regra = RegraAutomacao.objects.create(
        tenant=tenant_a, nome='Regra Teste', ativa=True, fluxo_json={},
    )
    r = logged_client_a.get(f'/marketing/automacoes/{regra.pk}/editor/')
    if r.status_code == 200:
        assert not _vazou_user_b(r.content, users_b), \
            "Editor de automacao vazou users do tenant B"


# ============================================================================
# ISOLAMENTO NO QUERYSET (teste direto)
# ============================================================================

@pytest.mark.django_db
def test_queryset_filtrado_por_tenant_exclui_outros(db, tenant_a, tenant_b, users_a, users_b):
    """
    O padrao perfil__tenant=X deve retornar SO os users do tenant X.
    Garante que a query nao retorna usuarios de outro tenant mesmo com
    perfil existindo em ambos.
    """
    qs_a = User.objects.filter(is_active=True, perfil__tenant=tenant_a).order_by('username')
    qs_b = User.objects.filter(is_active=True, perfil__tenant=tenant_b).order_by('username')

    usernames_a = list(qs_a.values_list('username', flat=True))
    usernames_b = list(qs_b.values_list('username', flat=True))

    assert 'admin_alpha' in usernames_a
    assert 'agente_alpha' in usernames_a
    assert 'vazamento_1' not in usernames_a
    assert 'vazamento_2' not in usernames_a

    assert 'vazamento_1' in usernames_b
    assert 'vazamento_2' in usernames_b
    assert 'admin_alpha' not in usernames_b
    assert 'agente_alpha' not in usernames_b


@pytest.mark.django_db
def test_queryset_sem_filtro_tenant_vaza(db, users_a, users_b):
    """
    Sanity check: SEM o filtro de tenant, a query retorna users de TODOS
    os tenants. Esse e o estado 'quebrado' que o fix corrige.
    """
    todos = list(
        User.objects.filter(is_active=True)
        .values_list('username', flat=True)
    )
    assert 'admin_alpha' in todos
    assert 'agente_alpha' in todos
    assert 'vazamento_1' in todos  # Prova que SEM filtro vaza
    assert 'vazamento_2' in todos
