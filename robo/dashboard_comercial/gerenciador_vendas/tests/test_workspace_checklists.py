"""Testes da tela de gestao de Checklists do Workspace.

Cobre: permissao (workspace.ver / workspace.editar_todos), isolamento
multi tenant, CRUD do Checklist (incl. slug duplicado), CRUD do ItemChecklist
(incl. o contrato do Matrix via `full_clean()` no `item_salvar` — o teste mais
importante: prova que a tela nao deixa passar 6+ opcoes) e reordenacao
via drag and drop (`itens_ordenar`).

Segue o padrao de tests/test_workspace_propostas.py (mk_user + set_current_tenant).
"""
import json

import pytest
from django.urls import reverse

from apps.automacao.models import Checklist, ItemChecklist
from apps.sistema.middleware import set_current_tenant
from apps.sistema.models import Funcionalidade, PerfilPermissao, PermissaoUsuario
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
    t = TenantFactory(nome='Aurora Checklist Teste', slug='aurora-checklist-teste')
    ConfigEmpresaFactory(tenant=t)
    set_current_tenant(t)
    yield t
    set_current_tenant(None)


def _mk_checklist(tenant, **kwargs):
    defaults = {'nome': 'Roteiro de venda', 'slug': 'roteiro-venda'}
    defaults.update(kwargs)
    return Checklist.all_tenants.create(tenant=tenant, **defaults)


# ============================================================================
# Permissao + isolamento de tenant
# ============================================================================

@pytest.mark.django_db
def test_lista_exige_workspace_ver(client, tenant):
    client.force_login(mk_user(tenant))  # sem workspace.ver
    r = client.get(reverse('workspace:checklists_lista'))
    assert r.status_code == 403


@pytest.mark.django_db
def test_lista_mostra_apenas_do_proprio_tenant(client, tenant):
    _mk_checklist(tenant, nome='Roteiro do tenant A', slug='roteiro-a')
    outro = TenantFactory(nome='Outro provedor', slug='outro-checklist')
    ConfigEmpresaFactory(tenant=outro)
    _mk_checklist(outro, nome='Roteiro do tenant B', slug='roteiro-b')

    client.force_login(mk_user(tenant, 'workspace.ver'))
    r = client.get(reverse('workspace:checklists_lista'))
    assert r.status_code == 200
    assert b'Roteiro do tenant A' in r.content
    assert b'Roteiro do tenant B' not in r.content


# ============================================================================
# CRUD do Checklist
# ============================================================================

@pytest.mark.django_db
def test_salvar_cria_e_atualiza(client, tenant):
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))

    r = client.post(reverse('workspace:checklist_salvar'), {
        'nome': 'Roteiro visita tecnica',
        'slug': 'roteiro-visita',
        'contexto': 'visita_tecnica',
        'modo_preenchimento': 'humano',
        'entidade_alvo': 'oportunidade',
        'ativo': 'on',
    })
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is True
    checklist_id = data['id']

    checklist = Checklist.all_tenants.get(pk=checklist_id)
    assert checklist.nome == 'Roteiro visita tecnica'
    assert checklist.contexto == 'visita_tecnica'
    assert checklist.modo_preenchimento == 'humano'
    assert checklist.entidade_alvo == 'oportunidade'

    r2 = client.post(reverse('workspace:checklist_salvar'), {
        'id': checklist_id,
        'nome': 'Roteiro visita tecnica (atualizado)',
        'slug': 'roteiro-visita',
        'contexto': 'visita_tecnica',
        'modo_preenchimento': 'ambos',
        'entidade_alvo': 'oportunidade',
        # 'ativo' ausente = desmarcado
    })
    assert r2.status_code == 200
    checklist.refresh_from_db()
    assert checklist.nome == 'Roteiro visita tecnica (atualizado)'
    assert checklist.modo_preenchimento == 'ambos'
    assert checklist.ativo is False


@pytest.mark.django_db
def test_salvar_slug_duplicado_no_mesmo_tenant_da_erro(client, tenant):
    _mk_checklist(tenant, nome='Original', slug='meu-slug')
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))

    r = client.post(reverse('workspace:checklist_salvar'), {
        'nome': 'Outro checklist',
        'slug': 'meu-slug',
    })
    assert r.status_code == 400
    assert 'erro' in r.json()
    assert Checklist.all_tenants.filter(tenant=tenant, slug='meu-slug').count() == 1


@pytest.mark.django_db
def test_excluir_remove_o_checklist(client, tenant):
    checklist = _mk_checklist(tenant)
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))

    r = client.post(reverse('workspace:checklist_excluir', args=[checklist.pk]))
    assert r.status_code == 200
    assert r.json()['ok'] is True
    assert not Checklist.all_tenants.filter(pk=checklist.pk).exists()


# ============================================================================
# Itens — o full_clean() protege o contrato com o Matrix
# ============================================================================

@pytest.mark.django_db
def test_item_salvar_com_seis_opcoes_retorna_400_com_mensagem_do_clean(client, tenant):
    """O flow do Matrix so tem branch pronto pra 2 a 5 opcoes — o `clean()` do
    ItemChecklist bloqueia 6+. Prova que a view chama `full_clean()` de verdade
    (nao so confia no front) e devolve a mensagem, sem engolir."""
    checklist = _mk_checklist(tenant)
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))

    payload = {
        'chave': 'plano',
        'pergunta': 'Qual plano voce quer?',
        'tipo_resposta': 'opcoes',
        'opcoes': [{'texto': f'Opcao {i}'} for i in range(1, 7)],  # 6 opcoes
    }
    r = client.post(
        reverse('workspace:checklist_item_salvar', args=[checklist.pk]),
        data=json.dumps(payload), content_type='application/json',
    )
    assert r.status_code == 400
    erro = r.json()['erro']
    assert 'matrix' in erro.lower()
    assert not ItemChecklist.all_tenants.filter(checklist=checklist, chave='plano').exists()


@pytest.mark.django_db
def test_item_salvar_com_tres_opcoes_cria(client, tenant):
    checklist = _mk_checklist(tenant)
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))

    payload = {
        'chave': 'plano',
        'pergunta': 'Qual plano voce quer?',
        'tipo_resposta': 'opcoes',
        'opcoes': [
            {'texto': 'Plano 300MB', 'valor': '300mb'},
            {'texto': 'Plano 600MB', 'valor': '600mb'},
            {'texto': 'Plano 1GB', 'valor': '1gb'},
        ],
    }
    r = client.post(
        reverse('workspace:checklist_item_salvar', args=[checklist.pk]),
        data=json.dumps(payload), content_type='application/json',
    )
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is True

    item = ItemChecklist.all_tenants.get(pk=data['id'])
    assert item.chave == 'plano'
    assert item.tipo_resposta == 'opcoes'
    assert len(item.opcoes) == 3
    assert item.checklist_id == checklist.pk


@pytest.mark.django_db
def test_item_salvar_regex_invalido_retorna_400(client, tenant):
    checklist = _mk_checklist(tenant)
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))

    payload = {
        'chave': 'cep',
        'pergunta': 'Qual seu CEP?',
        'tipo_validacao': 'regex',
        'regex_validacao': '(',  # regex invalido de proposito
    }
    r = client.post(
        reverse('workspace:checklist_item_salvar', args=[checklist.pk]),
        data=json.dumps(payload), content_type='application/json',
    )
    assert r.status_code == 400
    assert 'regex' in r.json()['erro'].lower()


@pytest.mark.django_db
def test_item_excluir_remove(client, tenant):
    checklist = _mk_checklist(tenant)
    item = ItemChecklist.all_tenants.create(
        tenant=tenant, checklist=checklist, chave='cep', pergunta='Qual seu CEP?', ordem=0,
    )
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))

    r = client.post(reverse('workspace:checklist_item_excluir', args=[item.pk]))
    assert r.status_code == 200
    assert r.json()['ok'] is True
    assert not ItemChecklist.all_tenants.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_itens_ordenar_reordena(client, tenant):
    checklist = _mk_checklist(tenant)
    i1 = ItemChecklist.all_tenants.create(tenant=tenant, checklist=checklist, chave='um', pergunta='Um?', ordem=0)
    i2 = ItemChecklist.all_tenants.create(tenant=tenant, checklist=checklist, chave='dois', pergunta='Dois?', ordem=1)
    i3 = ItemChecklist.all_tenants.create(tenant=tenant, checklist=checklist, chave='tres', pergunta='Tres?', ordem=2)

    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))
    nova_ordem = [i3.pk, i1.pk, i2.pk]
    r = client.post(
        reverse('workspace:checklist_itens_ordenar', args=[checklist.pk]),
        data=json.dumps({'ids': nova_ordem}), content_type='application/json',
    )
    assert r.status_code == 200
    assert r.json()['ok'] is True

    i1.refresh_from_db(); i2.refresh_from_db(); i3.refresh_from_db()
    assert i3.ordem == 0
    assert i1.ordem == 1
    assert i2.ordem == 2


@pytest.mark.django_db
def test_pagina_novo_renderiza_sem_pk(client, tenant):
    """Tela de NOVO checklist (sem pk) precisa renderizar.

    Regressao: o template montava `{% url ... checklist.pk %}` pros endpoints de
    item, e o `{% url %}` e resolvido pelo Django ANTES do JS rodar, entao o
    guard de CHECKLIST_ID no script nao evitava o NoReverseMatch.
    """
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))
    r = client.get(reverse('workspace:checklist_novo'))
    assert r.status_code == 200


@pytest.mark.django_db
def test_pagina_editar_renderiza_com_pk(client, tenant):
    """Contraparte: com checklist salvo, a tela abre e traz os endpoints de item."""
    checklist = _mk_checklist(tenant)
    ItemChecklist.all_tenants.create(
        tenant=tenant, checklist=checklist, chave='cep', pergunta='Qual o CEP?', ordem=0)
    client.force_login(mk_user(tenant, 'workspace.ver', 'workspace.editar_todos'))
    r = client.get(reverse('workspace:checklist_editar', args=[checklist.pk]))
    assert r.status_code == 200
    assert 'Qual o CEP?' in r.content.decode()
