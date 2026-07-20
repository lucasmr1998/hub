"""
Testes do gating do modulo People: contratacao, permissao e navegacao.

Este e o assunto que mais falha em silencio no registro de um modulo novo. Os
tres modos de falha, todos com teste aqui:

1. Esquecer a property `acesso_people` no PermissaoUsuario. O middleware usa
   getattr com default False, entao o modulo inteiro passa a devolver 403 sem
   nenhum erro de import pra denunciar.
2. Esquecer o publish no context processor. `modulo_people` fica indefinido no
   template, o `{% if %}` da sidebar da falso, e o item nunca aparece apesar de
   o tenant ter contratado.
3. Confundir contratacao com permissao. Sao gates diferentes e o sistema so
   aplica o segundo.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.people.models import Unidade
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PermissaoUsuario,
    PerfilUsuario, Plano,
)
from tests.factories import TenantFactory


def _tenant_com_people(**kwargs):
    tenant = TenantFactory(modulo_people=True, **kwargs)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant, nome_empresa=tenant.nome, ativo=True)
    return tenant


def _usuario(tenant, username, *, funcionalidades=(), superuser=False):
    user = User.objects.create_user(username=username, password='x', is_superuser=superuser,
                                    is_staff=superuser)
    PerfilUsuario.objects.create(user=user, tenant=tenant)
    if funcionalidades is not None:
        perfil = PerfilPermissao.objects.create(tenant=tenant, nome=f'Perfil {username}')
        for codigo in funcionalidades:
            func, _ = Funcionalidade.objects.get_or_create(
                codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
            perfil.funcionalidades.add(func)
        PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil)
    return user


def _logado(user):
    cliente = Client()
    cliente.force_login(user)
    return cliente


# ──────────────────────────────────────────────
# Permissao por funcionalidade
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_usuario_com_funcionalidade_acessa():
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])
    assert _logado(user).get('/people/').status_code == 200


@pytest.mark.django_db
def test_usuario_sem_funcionalidade_recebe_403():
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'vendedor', funcionalidades=[])
    assert _logado(user).get('/people/').status_code == 403


@pytest.mark.django_db
def test_property_acesso_people_existe_e_funciona():
    """
    Se esta property faltar, `getattr(perm, 'acesso_people', False)` no
    middleware devolve False e o modulo inteiro vira 403, sem erro de import
    pra denunciar. E o modo de falha mais traicoeiro do registro de modulo.
    """
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])
    perm = PermissaoUsuario.objects.get(user=user)
    assert perm.acesso_people is True

    sem = _usuario(tenant, 'outro', funcionalidades=[])
    assert PermissaoUsuario.objects.get(user=sem).acesso_people is False


@pytest.mark.django_db
def test_sem_login_redireciona():
    assert Client().get('/people/').status_code == 302


# ──────────────────────────────────────────────
# Contratacao do modulo
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_tenant_sem_o_modulo_nao_entra_nem_com_permissao():
    """
    Contratacao e permissao sao gates diferentes. O middleware do sistema so
    aplica o segundo, e sem esta guarda o cliente que nao comprou People entra
    digitando a URL.
    """
    tenant = TenantFactory(modulo_people=False)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant, nome_empresa=tenant.nome, ativo=True)
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])

    resposta = _logado(user).get('/people/')
    assert resposta.status_code == 403
    assert b'nao contratou' in resposta.content


@pytest.mark.django_db
def test_superuser_tambem_respeita_a_contratacao():
    """Se o tenant nao tem o modulo, nao ha o que inspecionar ali."""
    tenant = TenantFactory(modulo_people=False)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant, nome_empresa=tenant.nome, ativo=True)
    user = _usuario(tenant, 'adm', funcionalidades=[], superuser=True)

    assert _logado(user).get('/people/').status_code == 403


@pytest.mark.django_db
def test_superuser_de_tenant_com_modulo_entra():
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'adm', funcionalidades=[], superuser=True)
    assert _logado(user).get('/people/').status_code == 200


# ──────────────────────────────────────────────
# Context processor e navegacao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_context_publica_modulo_people():
    """
    Sem o publish, `modulo_people` fica indefinido no template, o `{% if %}` da
    sidebar da falso, e o item nunca aparece apesar de contratado.
    """
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])

    resposta = _logado(user).get('/people/')
    assert resposta.context['modulo_people'] is True
    assert resposta.context['plano_people'] == 'starter'


@pytest.mark.django_db
def test_modulo_atual_e_people():
    """
    O branch precisa vir ANTES do check de url_name == 'dashboard' no
    _detectar_modulo_atual, senao aquele sequestra e o submenu errado abre.
    """
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])

    resposta = _logado(user).get('/people/')
    assert resposta.context['modulo_atual'] == 'people'


@pytest.mark.django_db
def test_sidebar_mostra_o_item_quando_contratado():
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])

    corpo = _logado(user).get('/people/').content.decode()
    assert 'data-module="people"' in corpo


@pytest.mark.django_db
def test_sidebar_esconde_o_item_de_quem_nao_tem_permissao():
    """Contratado pelo tenant, mas o usuario nao tem a funcionalidade."""
    tenant = _tenant_com_people()
    _usuario(tenant, 'gestora', funcionalidades=['people.ver'])
    sem = _usuario(tenant, 'vendedor', funcionalidades=[])

    corpo = _logado(sem).get('/').content.decode()
    assert 'data-module="people"' not in corpo


@pytest.mark.django_db
def test_flyout_tem_entrada_de_people():
    """
    O Workspace pulou este passo e ate hoje nao abre nada com a sidebar
    colapsada, porque o renderFlyout faz early return quando a chave nao existe.
    """
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])

    corpo = _logado(user).get('/people/').content.decode()
    assert "people: { title: 'People'" in corpo


@pytest.mark.django_db
def test_subnav_lista_as_paginas_do_modulo():
    tenant = _tenant_com_people()
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])

    corpo = _logado(user).get('/people/').content.decode()
    assert '/people/unidades/' in corpo


@pytest.mark.django_db
def test_pagina_de_unidades_responde():
    tenant = _tenant_com_people()
    Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro', codigo='loja-centro')
    user = _usuario(tenant, 'gestora', funcionalidades=['people.ver'])

    resposta = _logado(user).get('/people/unidades/')
    assert resposta.status_code == 200
    assert b'Loja Centro' in resposta.content


# ──────────────────────────────────────────────
# Coerencia do registro
# ──────────────────────────────────────────────

def test_people_e_modulo_de_plano():
    assert 'people' in [m for m, _ in Plano.MODULO_CHOICES]


def test_people_e_modulo_de_funcionalidade():
    assert 'people' in [m for m, _ in Funcionalidade.MODULO_CHOICES]


def test_middleware_mapeia_a_rota():
    from apps.sistema.middleware import _MODULO_MAP
    assert ('/people/', 'acesso_people') in _MODULO_MAP


def test_criar_tenant_aceita_people():
    """MODULOS_VALIDOS deriva de Plano.MODULO_CHOICES, entao modulo novo entra
    sozinho na validacao, nos argumentos --tier-* e nos kwargs do Tenant."""
    from apps.sistema.management.commands.criar_tenant import MODULOS_VALIDOS
    assert 'people' in MODULOS_VALIDOS


@pytest.mark.django_db
def test_tenant_tem_os_campos_de_contratacao():
    tenant = TenantFactory()
    assert hasattr(tenant, 'modulo_people')
    assert hasattr(tenant, 'plano_people')
    assert hasattr(tenant, 'plano_people_ref')
    assert tenant.tem_modulo('people') is False
    tenant.modulo_people = True
    assert tenant.tem_modulo('people') is True


@pytest.mark.django_db
def test_features_ativas_cobre_todos_os_modulos_do_plano():
    """
    As duas listas de modulo em tem_feature e features_ativas eram hardcoded e
    ja tinham esquecido modulo antes. Agora derivam de Plano.MODULO_CHOICES.
    """
    tenant = TenantFactory()
    plano = Plano.objects.create(nome='People Pro', modulo='people', tier='pro', ativo=True)
    plano.features.create(nome='Board', slug='people-board', ativo=True)
    tenant.plano_people_ref = plano
    tenant.save()

    assert tenant.tem_feature('people-board') is True
    assert 'people-board' in tenant.features_ativas()
