"""
Testes de hardening da engine de automação (E1).

Cobre:
- Gates de permissão granular (`automacao.ver` / `automacao.gerenciar`) nos
  endpoints do editor: usuário sem a funcionalidade recebe 403; superuser passa.
- Robustez do webhook público: grafo inválido devolve 400 (não 500).

Usa o Client do Django (login de sessão) pra passar pelo middleware de verdade
(TenantMiddleware injeta `request.tenant`, PermissaoMiddleware injeta
`request.user_funcionalidades`) — igual ao padrão de test_module_access.py.
"""
import json

import pytest

from apps.automacao.models import Fluxo
from apps.sistema.models import PerfilPermissao, PermissaoUsuario
from tests.factories import ConfigEmpresaFactory, PerfilFactory, TenantFactory, UserFactory


@pytest.fixture
def tenant(db):
    t = TenantFactory(slug='automacao-e1', nome='Automacao E1')
    ConfigEmpresaFactory(tenant=t)
    return t


@pytest.fixture
def usuario_sem_permissao(db, tenant):
    """Usuário logado, com tenant, mas com um perfil de permissão VAZIO (sem
    nenhuma funcionalidade `automacao.*`). Sem um `PermissaoUsuario` cadastrado
    o sistema trata como legado (tudo liberado) — por isso o perfil vazio é
    obrigatório aqui pra realmente testar o bloqueio."""
    user = UserFactory()
    PerfilFactory(user=user, tenant=tenant)
    perfil_vazio = PerfilPermissao.objects.create(tenant=tenant, nome='Sem automação')
    PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil_vazio)
    return user


@pytest.fixture
def superuser(db, tenant):
    user = UserFactory(is_superuser=True, is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    return user


# ============================================================================
# Gates de permissão
# ============================================================================

@pytest.mark.django_db
def test_testar_fluxo_sem_permissao_403(client, usuario_sem_permissao):
    client.force_login(usuario_sem_permissao)
    r = client.post(
        '/automacao/api/testar-fluxo/',
        data=json.dumps({'fluxo': {}}),
        content_type='application/json',
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_fluxos_post_sem_permissao_403(client, usuario_sem_permissao):
    client.force_login(usuario_sem_permissao)
    r = client.post(
        '/automacao/api/fluxos/',
        data=json.dumps({'nome': 'Fluxo sem permissão'}),
        content_type='application/json',
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_fluxos_get_sem_ver_403(client, usuario_sem_permissao):
    """GET exige `automacao.ver` (mesmo perfil bloqueado de POST tb bloqueia GET)."""
    client.force_login(usuario_sem_permissao)
    r = client.get('/automacao/api/fluxos/')
    assert r.status_code == 403


@pytest.mark.django_db
def test_fluxos_get_superuser_ok(client, superuser):
    client.force_login(superuser)
    r = client.get('/automacao/api/fluxos/')
    assert r.status_code == 200


# ============================================================================
# Robustez do webhook público (fluxo inválido não pode derrubar o endpoint)
# ============================================================================

@pytest.mark.django_db
def test_webhook_grafo_invalido_devolve_400(client, tenant):
    fluxo = Fluxo.objects.create(
        tenant=tenant,
        nome='Fluxo quebrado',
        ativo=True,
        grafo={'inicio': 'x', 'nodes': {}},
        webhook_token='tok-e1-grafo-quebrado',
    )
    r = client.post(
        f'/automacao/webhook/{fluxo.webhook_token}/',
        data=json.dumps({'a': 1}),
        content_type='application/json',
    )
    assert r.status_code == 400
    assert 'fluxo inválido' in r.json()['erro']
