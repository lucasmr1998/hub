"""Testes do nó `carregar_lead`.

Este nó fecha o "gap do lead" do bot de vendas (ver
`apps/automacao/management/commands/seed_fluxo_bot_venda.py`): o gatilho
`webhook` genérico só hidrata `{{var.payload}}`, nunca uma entidade de
domínio, e os nós de checklist exigem `contexto.lead`. Cobre: achar por
lead_id, achar por telefone (com/sem 55 e DDD), criar quando configurado,
não criar por padrão, e a injeção de `contexto.lead` via
`NodeResult.entidades` (mecanismo genérico em `nodes/base.py`/`context.py`).
"""
import pytest

from apps.automacao.models import Checklist, ItemChecklist
from apps.automacao.nodes import Contexto, tipo_por_slug
from apps.comercial.leads.models import LeadProspecto
from tests.factories import LeadProspectoFactory, TenantFactory


def _no():
    return tipo_por_slug('carregar_lead')


def _ctx(tenant, **kwargs):
    return Contexto(tenant=tenant, **kwargs)


def test_registrado_no_registry():
    assert _no() is not None


def test_config_sem_telefone_e_sem_lead_id_e_invalida():
    erros = _no().validar_config({})
    assert erros


def test_config_so_com_telefone_e_valida():
    assert _no().validar_config({'telefone': '{{var.payload.cellphone}}'}) == []


# ──────────────────────────────────────────────
# achar por lead_id
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_achar_por_lead_id():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    ctx = _ctx(tenant)

    res = _no().executar({'lead_id': str(lead.pk)}, {}, ctx)

    assert res.branch == 'encontrado'
    assert res.output['lead_id'] == lead.pk
    assert res.output['criado'] is False
    assert res.entidades == {'lead': lead}


@pytest.mark.django_db
def test_lead_id_nao_encontrado_nao_cai_pro_telefone():
    tenant = TenantFactory()
    # Lead existe com esse telefone, mas o lead_id pedido não bate com nada:
    # não deve "adivinhar" pelo telefone (ancoraria a conversa errada).
    LeadProspectoFactory(tenant=tenant, telefone='558999990001')

    res = _no().executar(
        {'lead_id': '999999', 'telefone': '558999990001'}, {}, _ctx(tenant))

    assert res.branch == 'nao_encontrado'
    assert res.output['lead_id'] is None
    assert res.entidades is None


@pytest.mark.django_db
def test_lead_id_de_outro_tenant_nao_acha():
    tenant_a = TenantFactory()
    tenant_b = TenantFactory()
    lead_b = LeadProspectoFactory(tenant=tenant_b)

    res = _no().executar({'lead_id': str(lead_b.pk)}, {}, _ctx(tenant_a))

    assert res.branch == 'nao_encontrado'


# ──────────────────────────────────────────────
# achar por telefone (tolerante a 55/DDD)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_achar_por_telefone_exato():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, telefone='558999990001')

    res = _no().executar({'telefone': '558999990001'}, {}, _ctx(tenant))

    assert res.branch == 'encontrado'
    assert res.output['lead_id'] == lead.pk


@pytest.mark.django_db
def test_achar_por_telefone_com_55_quando_salvo_sem_55():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, telefone='89999990001')

    res = _no().executar({'telefone': '5589999990001'}, {}, _ctx(tenant))

    assert res.branch == 'encontrado'
    assert res.output['lead_id'] == lead.pk


@pytest.mark.django_db
def test_achar_por_telefone_sem_ddd_quando_salvo_com_ddd_e_55():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, telefone='5589999990001')

    # payload manda só o número local (sem 55, sem DDD)
    res = _no().executar({'telefone': '999990001'}, {}, _ctx(tenant))

    assert res.branch == 'encontrado'
    assert res.output['lead_id'] == lead.pk


@pytest.mark.django_db
def test_telefone_resolve_template_do_payload():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, telefone='558999990001')
    ctx = _ctx(tenant, variaveis={'payload': {'cellphone': '558999990001'}})

    res = _no().executar({'telefone': '{{var.payload.cellphone}}'}, {}, ctx)

    assert res.branch == 'encontrado'
    assert res.output['lead_id'] == lead.pk


# ──────────────────────────────────────────────
# criar quando não existir
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_nao_acha_e_nao_cria_por_padrao():
    tenant = TenantFactory()

    res = _no().executar({'telefone': '558999990002'}, {}, _ctx(tenant))

    assert res.branch == 'nao_encontrado'
    assert res.entidades is None
    assert not LeadProspecto.all_tenants.filter(tenant=tenant).exists()


@pytest.mark.django_db
def test_criar_se_nao_existir_cria_lead_minimo():
    tenant = TenantFactory()

    res = _no().executar(
        {'telefone': '558999990003', 'criar_se_nao_existir': True}, {}, _ctx(tenant))

    assert res.branch == 'encontrado'
    assert res.output['criado'] is True
    lead = LeadProspecto.all_tenants.get(tenant=tenant, telefone='558999990003')
    assert res.output['lead_id'] == lead.pk
    assert lead.origem == 'whatsapp'
    assert 'Lead WhatsApp' in lead.nome_razaosocial
    assert res.entidades == {'lead': lead}


@pytest.mark.django_db
def test_criar_se_nao_existir_usa_nome_do_payload_quando_ha():
    tenant = TenantFactory()
    ctx = _ctx(tenant, variaveis={'payload': {'cellphone': '558999990004', 'name': 'Maria Teste'}})

    res = _no().executar(
        {'telefone': '{{var.payload.cellphone}}', 'criar_se_nao_existir': True}, {}, ctx)

    assert res.branch == 'encontrado'
    lead = LeadProspecto.all_tenants.get(tenant=tenant, telefone='558999990004')
    assert lead.nome_razaosocial == 'Maria Teste'


@pytest.mark.django_db
def test_criar_se_nao_existir_nao_duplica_quando_ja_existe():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, telefone='558999990005')

    res = _no().executar(
        {'telefone': '558999990005', 'criar_se_nao_existir': True}, {}, _ctx(tenant))

    assert res.output['criado'] is False
    assert res.output['lead_id'] == lead.pk
    assert LeadProspecto.all_tenants.filter(tenant=tenant, telefone='558999990005').count() == 1


# ──────────────────────────────────────────────
# erro
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_telefone_vazio_apos_resolver_e_sem_lead_id_vira_erro():
    tenant = TenantFactory()
    ctx = _ctx(tenant, variaveis={'payload': {}})

    res = _no().executar({'telefone': '{{var.payload.cellphone}}'}, {}, ctx)

    assert res.branch == 'erro'
    assert res.status == 'erro'


# ──────────────────────────────────────────────
# prova que o gap fechou: depois de `carregar_lead`, os nós de checklist funcionam
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_depois_de_carregar_lead_checklist_proximo_item_funciona():
    tenant = TenantFactory()
    checklist = Checklist.all_tenants.create(
        tenant=tenant, slug='bot-vendas-teste', nome='Bot', ativo=True)
    item = ItemChecklist.all_tenants.create(
        tenant=tenant, checklist=checklist, chave='cpf', ordem=1,
        pergunta='Qual seu CPF?', obrigatorio=True,
    )
    # Contexto SEM lead pré-injetado — só payload, exatamente como o caminho
    # HTTP real (`webhook_receber`) monta o Contexto.
    ctx = _ctx(tenant, variaveis={'payload': {'cellphone': '558999990006'}})

    res_lead = _no().executar(
        {'telefone': '{{var.payload.cellphone}}', 'criar_se_nao_existir': True}, {}, ctx)
    ctx.aplicar_resultado('hidratar', res_lead)

    assert ctx.lead is not None
    assert ctx.lead.telefone == '558999990006'

    res_proximo = tipo_por_slug('checklist_proximo_item').executar(
        {'checklist': checklist.slug, 'entidade': 'lead'}, {}, ctx)

    assert res_proximo.branch == 'tem_item'
    assert res_proximo.output['item_id'] == item.pk
