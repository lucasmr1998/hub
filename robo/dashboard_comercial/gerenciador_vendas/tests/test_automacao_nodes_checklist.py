"""Testes dos nós `checklist_proximo_item`, `checklist_validar` e
`checklist_progresso` (com DB: os 3 tocam Checklist/ItemChecklist/
RespostaChecklist via `apps.automacao.services.checklist`).

Estes nós são a ponte entre o checklist configurável (dado) e o grafo do
editor. A garantia central testada aqui é que nenhum deles chama LLM por
conta própria (ver `test_nenhum_no_de_checklist_chama_llm`): a decisão de
arquitetura foi orquestração via FLUXO usando o nó `ia_agente` já existente,
não um serviço Python com IA embutida.
"""
from types import SimpleNamespace
from unittest import mock

import pytest

from apps.automacao.models import Checklist, ItemChecklist, RespostaChecklist
from apps.automacao.nodes import Contexto, tipo_por_slug
from apps.automacao.services.checklist import registrar_resposta
from tests.factories import TenantFactory


def _checklist(tenant, **kwargs):
    defaults = {'nome': 'Bot de vendas', 'slug': 'bot-vendas', 'ativo': True}
    defaults.update(kwargs)
    return Checklist.all_tenants.create(tenant=tenant, **defaults)


def _item(tenant, checklist, chave, **kwargs):
    defaults = {'pergunta': f'Pergunta {chave}?', 'ordem': 1, 'obrigatorio': True}
    defaults.update(kwargs)
    return ItemChecklist.all_tenants.create(tenant=tenant, checklist=checklist, chave=chave, **defaults)


def _ctx(tenant, **kwargs):
    return Contexto(tenant=tenant, **kwargs)


def _no(tipo):
    return tipo_por_slug(tipo)


# ──────────────────────────────────────────────
# registro
# ──────────────────────────────────────────────

def test_registrados_no_registry():
    assert _no('checklist_proximo_item') is not None
    assert _no('checklist_validar') is not None
    assert _no('checklist_progresso') is not None


# ──────────────────────────────────────────────
# checklist_proximo_item
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_proximo_item_com_pendente_retorna_tem_item_e_output_completo():
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    _item(tenant, checklist, 'cpf', pergunta='Qual seu CPF?', ordem=1,
          tipo_resposta='texto_livre', tipo_validacao='cpf_cnpj')
    lead = SimpleNamespace(pk=10)

    res = _no('checklist_proximo_item').executar(
        {'checklist': checklist.slug, 'entidade': 'lead'}, {}, _ctx(tenant, lead=lead))

    assert res.branch == 'tem_item'
    assert res.output['chave'] == 'cpf'
    assert res.output['pergunta'] == 'Qual seu CPF?'
    assert res.output['tipo_resposta'] == 'texto_livre'
    assert res.output['tipo_validacao'] == 'cpf_cnpj'
    assert res.output['opcoes'] == []
    assert res.output['ura_titulo'] == ''
    assert res.output['instrucoes_ia'] == ''
    assert res.output['ordem'] == 1
    assert 'item_id' in res.output


@pytest.mark.django_db
def test_proximo_item_tudo_respondido_retorna_completo():
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    item = _item(tenant, checklist, 'cpf', tipo_validacao='cpf_cnpj')
    lead = SimpleNamespace(pk=11)
    registrar_resposta(checklist, item, 'lead', lead.pk, '11144477735', valor_processado='11144477735')

    res = _no('checklist_proximo_item').executar(
        {'checklist': checklist.slug, 'entidade': 'lead'}, {}, _ctx(tenant, lead=lead))

    assert res.branch == 'completo'


def test_proximo_item_sem_entidade_vira_erro():
    tenant = SimpleNamespace(pk=1, slug='alpha')
    res = _no('checklist_proximo_item').executar(
        {'checklist': 'x', 'entidade': 'lead'}, {}, _ctx(tenant))
    assert res.branch == 'erro'
    assert 'lead' in (res.erro or '').lower()


# ──────────────────────────────────────────────
# checklist_validar
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_validar_opcao_por_numero_marca_valida_e_grava():
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    item = _item(tenant, checklist, 'plano', tipo_resposta='opcoes',
                 opcoes=[{'texto': 'Fibra 300'}, {'texto': 'Fibra 500'}])
    lead = SimpleNamespace(pk=20)

    res = _no('checklist_validar').executar(
        {'checklist': checklist.slug, 'item_id': item.pk, 'resposta': '1', 'entidade': 'lead'},
        {}, _ctx(tenant, lead=lead))

    assert res.branch == 'valida'
    assert res.output['valida'] is True
    assert res.output['valor_processado'] == 'Fibra 300'
    assert res.output['chave'] == 'plano'
    assert RespostaChecklist.objects.filter(item=item, entidade_id=lead.pk, entidade_tipo='lead').exists()


@pytest.mark.django_db
def test_validar_opcao_por_texto_marca_valida_e_grava():
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    item = _item(tenant, checklist, 'plano', tipo_resposta='opcoes',
                 opcoes=[{'texto': 'Fibra 300'}, {'texto': 'Fibra 500'}])
    lead = SimpleNamespace(pk=21)

    res = _no('checklist_validar').executar(
        {'checklist': checklist.slug, 'item_id': item.pk, 'resposta': 'Fibra 500', 'entidade': 'lead'},
        {}, _ctx(tenant, lead=lead))

    assert res.branch == 'valida'
    assert res.output['valor_processado'] == 'Fibra 500'
    assert RespostaChecklist.objects.filter(item=item, entidade_id=lead.pk).exists()


@pytest.mark.django_db
def test_validar_opcao_invalida_marca_invalida_e_nao_grava():
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    item = _item(tenant, checklist, 'plano', tipo_resposta='opcoes',
                 opcoes=[{'texto': 'Fibra 300'}, {'texto': 'Fibra 500'}])
    lead = SimpleNamespace(pk=22)

    res = _no('checklist_validar').executar(
        {'checklist': checklist.slug, 'item_id': item.pk, 'resposta': 'Fibra 9000', 'entidade': 'lead'},
        {}, _ctx(tenant, lead=lead))

    assert res.branch == 'invalida'
    assert res.output['valida'] is False
    assert not RespostaChecklist.objects.filter(item=item).exists()


@pytest.mark.django_db
def test_validar_registrar_false_nao_grava_mesmo_valida():
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    item = _item(tenant, checklist, 'plano', tipo_resposta='opcoes',
                 opcoes=[{'texto': 'Fibra 300'}, {'texto': 'Fibra 500'}])
    lead = SimpleNamespace(pk=23)

    res = _no('checklist_validar').executar(
        {'checklist': checklist.slug, 'item_id': item.pk, 'resposta': 'Fibra 300',
         'entidade': 'lead', 'registrar': False},
        {}, _ctx(tenant, lead=lead))

    assert res.branch == 'valida'
    assert not RespostaChecklist.objects.filter(item=item).exists()


@pytest.mark.django_db
def test_validar_item_de_outro_checklist_vira_erro():
    tenant = TenantFactory()
    checklist_a = _checklist(tenant, slug='checklist-a')
    checklist_b = _checklist(tenant, slug='checklist-b')
    item_b = _item(tenant, checklist_b, 'plano', tipo_resposta='opcoes',
                    opcoes=[{'texto': 'Fibra 300'}, {'texto': 'Fibra 500'}])
    lead = SimpleNamespace(pk=24)

    res = _no('checklist_validar').executar(
        {'checklist': checklist_a.slug, 'item_id': item_b.pk, 'resposta': 'Fibra 300', 'entidade': 'lead'},
        {}, _ctx(tenant, lead=lead))

    assert res.branch == 'erro'


def test_validar_sem_entidade_vira_erro():
    tenant = SimpleNamespace(pk=1, slug='alpha')
    res = _no('checklist_validar').executar(
        {'checklist': 'x', 'item_id': 1, 'resposta': 'a'}, {}, _ctx(tenant))
    assert res.branch == 'erro'


# ──────────────────────────────────────────────
# checklist_progresso
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_progresso_percentual_e_faltando_corretos():
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    item1 = _item(tenant, checklist, 'cpf', ordem=1)
    _item(tenant, checklist, 'email', ordem=2)
    lead = SimpleNamespace(pk=30)
    registrar_resposta(checklist, item1, 'lead', lead.pk, '11144477735', valor_processado='11144477735')

    res = _no('checklist_progresso').executar(
        {'checklist': checklist.slug, 'entidade': 'lead'}, {}, _ctx(tenant, lead=lead))

    assert res.branch == 'incompleto'
    assert res.output['total'] == 2
    assert res.output['respondidos'] == 1
    assert res.output['faltando'] == ['email']
    assert res.output['percentual'] == 50
    assert res.output['completo'] is False


@pytest.mark.django_db
def test_progresso_completo_quando_tudo_respondido():
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    item1 = _item(tenant, checklist, 'cpf', ordem=1)
    lead = SimpleNamespace(pk=31)
    registrar_resposta(checklist, item1, 'lead', lead.pk, '11144477735', valor_processado='11144477735')

    res = _no('checklist_progresso').executar(
        {'checklist': checklist.slug, 'entidade': 'lead'}, {}, _ctx(tenant, lead=lead))

    assert res.branch == 'completo'
    assert res.output['completo'] is True
    assert res.output['faltando'] == []


# ──────────────────────────────────────────────
# Garantia de arquitetura: nenhum nó de checklist chama LLM
# ──────────────────────────────────────────────

@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
def test_nenhum_no_de_checklist_chama_llm(mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _checklist(tenant)
    item = _item(tenant, checklist, 'plano', tipo_resposta='opcoes',
                 opcoes=[{'texto': 'Fibra 300'}, {'texto': 'Fibra 500'}])
    lead = SimpleNamespace(pk=40)

    _no('checklist_proximo_item').executar(
        {'checklist': checklist.slug, 'entidade': 'lead'}, {}, _ctx(tenant, lead=lead))
    _no('checklist_validar').executar(
        {'checklist': checklist.slug, 'item_id': item.pk, 'resposta': 'Fibra 300', 'entidade': 'lead'},
        {}, _ctx(tenant, lead=lead))
    _no('checklist_progresso').executar(
        {'checklist': checklist.slug, 'entidade': 'lead'}, {}, _ctx(tenant, lead=lead))

    mock_chamar_llm.assert_not_called()
