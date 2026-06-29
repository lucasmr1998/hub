"""Testes das Propostas do Workspace (Fase 2 dos agentes).

Cobre: a tool `solicitar_aprovacao` (agente cria proposta, tenant-safe), a fila de
aprovacao (permissoes ver/editar_todos), aprovar/rejeitar e isolamento de tenant.
"""
from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.sistema.middleware import set_current_tenant
from apps.sistema.models import Funcionalidade, PerfilPermissao, PermissaoUsuario
from apps.workspace.models import Proposta
from tests.factories import ConfigEmpresaFactory, PerfilFactory, TenantFactory, UserFactory


WS_FUNCS = {'workspace.ver': 'Ver Workspace', 'workspace.editar_todos': 'Editar todos'}


def _funcs(*codigos):
    out = []
    for c in codigos:
        f, _ = Funcionalidade.objects.get_or_create(
            codigo=c, defaults={'modulo': 'workspace', 'nome': WS_FUNCS.get(c, c)})
        out.append(f)
    return out


def mk_user(tenant, *codigos, is_superuser=False):
    user = UserFactory(is_staff=True, is_superuser=is_superuser)
    PerfilFactory(user=user, tenant=tenant)
    if not is_superuser:
        perfil = PerfilPermissao.objects.create(tenant=tenant, nome=f'Perfil {user.username}')
        if codigos:
            perfil.funcionalidades.add(*_funcs(*codigos))
        PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil)
    return user


@pytest.fixture
def tenant(db):
    t = TenantFactory(nome='Aurora Prop Teste', slug='aurora-prop-teste')
    ConfigEmpresaFactory(tenant=t)
    set_current_tenant(t)
    yield t
    set_current_tenant(None)


def _ctx(tenant):
    return SimpleNamespace(tenant=tenant, lead=None, variaveis={})


@pytest.mark.django_db
def test_tool_cria_proposta_pendente(tenant):
    from apps.automacao.services.ia_tools import despachar
    res = despachar('solicitar_aprovacao',
                    {'titulo': 'Pausar anuncio X', 'descricao': 'ROAS baixo', 'prioridade': 'alta'},
                    _ctx(tenant), None)
    assert 'registrada' in res
    p = Proposta.all_tenants.filter(tenant=tenant).first()
    assert p is not None
    assert p.titulo == 'Pausar anuncio X'
    assert p.prioridade == 'alta'
    assert p.status == 'pendente'


@pytest.mark.django_db
def test_tool_prioridade_invalida_vira_media(tenant):
    from apps.automacao.services.ia_tools import despachar
    despachar('solicitar_aprovacao',
              {'titulo': 'X', 'descricao': 'Y', 'prioridade': 'urgentissima'}, _ctx(tenant), None)
    assert Proposta.all_tenants.filter(tenant=tenant).first().prioridade == 'media'


@pytest.mark.django_db
def test_lista_exige_workspace_ver(client, tenant):
    client.force_login(mk_user(tenant))  # sem workspace.ver
    assert client.get(reverse('workspace:propostas_lista')).status_code == 403


@pytest.mark.django_db
def test_lista_mostra_pendentes(client, tenant):
    Proposta.objects.create(tenant=tenant, titulo='Prop visivel', descricao='d', status='pendente')
    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:propostas_lista'))
    assert r.status_code == 200
    assert b'Prop visivel' in r.content


@pytest.mark.django_db
def test_decidir_exige_editar_todos(client, tenant):
    p = Proposta.objects.create(tenant=tenant, titulo='P', descricao='d', status='pendente')
    client.force_login(mk_user(tenant, 'workspace.ver'))  # sem editar_todos
    r = client.post(reverse('workspace:proposta_decidir', args=[p.pk]), {'acao': 'aprovar'})
    assert r.status_code == 403
    p.refresh_from_db()
    assert p.status == 'pendente'


@pytest.mark.django_db
def test_aprovar_e_rejeitar(client, tenant):
    admin = mk_user(tenant, 'workspace.ver', 'workspace.editar_todos')
    client.force_login(admin)
    p1 = Proposta.objects.create(tenant=tenant, titulo='A', descricao='d', status='pendente')
    r = client.post(reverse('workspace:proposta_decidir', args=[p1.pk]), {'acao': 'aprovar'})
    assert r.status_code == 302
    p1.refresh_from_db()
    assert p1.status == 'aprovada'
    assert p1.decidido_por == admin
    p2 = Proposta.objects.create(tenant=tenant, titulo='B', descricao='d', status='pendente')
    client.post(reverse('workspace:proposta_decidir', args=[p2.pk]),
                {'acao': 'rejeitar', 'motivo': 'nao faz sentido'})
    p2.refresh_from_db()
    assert p2.status == 'rejeitada'
    assert p2.motivo_rejeicao == 'nao faz sentido'


@pytest.mark.django_db
def test_isolamento_tenant(tenant):
    Proposta.objects.create(tenant=tenant, titulo='do A', descricao='', status='pendente')
    t2 = TenantFactory(nome='Outro', slug='outro-prop')
    set_current_tenant(t2)
    try:
        assert Proposta.objects.filter(status='pendente').count() == 0
    finally:
        set_current_tenant(tenant)
