"""Testes do checklist configurável (Fase 1): validação de `ItemChecklist.clean()`
e o motor em `apps.automacao.services.checklist` (itens_elegiveis, proximo_item,
registrar_resposta, progresso). Sem HTTP — os endpoints ficam pra Fase 2."""
import pytest
from django.core.exceptions import ValidationError

from apps.automacao.models import Checklist, ItemChecklist, RespostaChecklist
from apps.automacao.services import checklist as checklist_service
from apps.comercial.leads.models import CampoCustomizado
from tests.factories import LeadProspectoFactory, OportunidadeVendaFactory, PipelineEstagioFactory, TenantFactory


def _criar_checklist(tenant, **kwargs):
    defaults = {'nome': 'Checklist de venda', 'slug': 'checklist-venda', 'contexto': 'bot_vendas'}
    defaults.update(kwargs)
    return Checklist.objects.create(tenant=tenant, **defaults)


def _criar_item(checklist, chave, ordem=0, **kwargs):
    defaults = {'pergunta': f'Pergunta {chave}?', 'ordem': ordem}
    defaults.update(kwargs)
    return ItemChecklist.objects.create(tenant=checklist.tenant, checklist=checklist, chave=chave, **defaults)


# ──────────────────────────────────────────────
# ItemChecklist.clean()
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_clean_rejeita_uma_unica_opcao():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='plano', pergunta='Qual plano?',
        tipo_resposta='opcoes', opcoes=[{'texto': 'Único'}],
    )
    with pytest.raises(ValidationError):
        item.clean()


@pytest.mark.django_db
def test_clean_rejeita_seis_opcoes():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    opcoes = [{'texto': f'Opção {i}'} for i in range(6)]
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='plano', pergunta='Qual plano?',
        tipo_resposta='opcoes', opcoes=opcoes,
    )
    with pytest.raises(ValidationError):
        item.clean()


@pytest.mark.django_db
@pytest.mark.parametrize('quantidade', [2, 5])
def test_clean_aceita_entre_duas_e_cinco_opcoes(quantidade):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    opcoes = [{'texto': f'Opção {i}', 'valor': str(i)} for i in range(quantidade)]
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='plano', pergunta='Qual plano?',
        tipo_resposta='opcoes', opcoes=opcoes,
    )
    item.clean()  # não levanta


@pytest.mark.django_db
def test_clean_rejeita_opcao_sem_texto():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='plano', pergunta='Qual plano?',
        tipo_resposta='opcoes', opcoes=[{'texto': 'Ok'}, {'valor': 'sem-texto'}],
    )
    with pytest.raises(ValidationError):
        item.clean()


@pytest.mark.django_db
def test_clean_rejeita_regex_invalido():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='cep', pergunta='Qual seu CEP?',
        tipo_validacao='regex', regex_validacao='[',
    )
    with pytest.raises(ValidationError):
        item.clean()


@pytest.mark.django_db
def test_clean_exige_regex_quando_tipo_validacao_regex():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='cep', pergunta='Qual seu CEP?',
        tipo_validacao='regex', regex_validacao='',
    )
    with pytest.raises(ValidationError):
        item.clean()


@pytest.mark.django_db
def test_clean_aceita_regex_valido():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='cep', pergunta='Qual seu CEP?',
        tipo_validacao='regex', regex_validacao=r'^\d{5}-?\d{3}$',
    )
    item.clean()  # não levanta


@pytest.mark.django_db
def test_clean_rejeita_ura_titulo_sem_opcoes():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='plano', pergunta='Qual plano?',
        tipo_resposta='texto_livre', ura_titulo='confirmacao_plano_620',
    )
    with pytest.raises(ValidationError):
        item.clean()


@pytest.mark.django_db
def test_clean_rejeita_condicao_sem_chave_ou_valor():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = ItemChecklist(
        tenant=tenant, checklist=checklist, chave='rua', pergunta='Qual a rua?',
        condicao={'chave': 'tem_endereco'},  # falta 'valor'
    )
    with pytest.raises(ValidationError):
        item.clean()


# ──────────────────────────────────────────────
# itens_elegiveis
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_itens_elegiveis_respeita_ordem():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'terceiro', ordem=2)
    _criar_item(checklist, 'primeiro', ordem=0)
    _criar_item(checklist, 'segundo', ordem=1)

    itens = checklist_service.itens_elegiveis(checklist, {})

    assert [i.chave for i in itens] == ['primeiro', 'segundo', 'terceiro']


@pytest.mark.django_db
def test_itens_elegiveis_ignora_item_inativo():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'ativo', ordem=0)
    _criar_item(checklist, 'inativo', ordem=1, ativo=False)

    itens = checklist_service.itens_elegiveis(checklist, {})

    assert [i.chave for i in itens] == ['ativo']


@pytest.mark.django_db
def test_itens_elegiveis_operador_igual():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'tipo_pessoa', ordem=0)
    _criar_item(checklist, 'cnpj', ordem=1, condicao={'chave': 'tipo_pessoa', 'operador': 'igual', 'valor': 'juridica'})

    assert [i.chave for i in checklist_service.itens_elegiveis(checklist, {'tipo_pessoa': 'juridica'})] == \
        ['tipo_pessoa', 'cnpj']
    assert [i.chave for i in checklist_service.itens_elegiveis(checklist, {'tipo_pessoa': 'fisica'})] == \
        ['tipo_pessoa']


@pytest.mark.django_db
def test_itens_elegiveis_operador_diferente():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'plano', ordem=0)
    _criar_item(checklist, 'motivo_recusa', ordem=1, condicao={'chave': 'plano', 'operador': 'diferente', 'valor': 'aceito'})

    assert [i.chave for i in checklist_service.itens_elegiveis(checklist, {'plano': 'recusado'})] == \
        ['plano', 'motivo_recusa']
    assert [i.chave for i in checklist_service.itens_elegiveis(checklist, {'plano': 'aceito'})] == ['plano']


@pytest.mark.django_db
def test_itens_elegiveis_operador_existe():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'cep', ordem=0)
    _criar_item(checklist, 'complemento', ordem=1, condicao={'chave': 'cep', 'operador': 'existe', 'valor': None})

    assert [i.chave for i in checklist_service.itens_elegiveis(checklist, {})] == ['cep']
    assert [i.chave for i in checklist_service.itens_elegiveis(checklist, {'cep': '64000-000'})] == \
        ['cep', 'complemento']


@pytest.mark.django_db
def test_itens_elegiveis_operador_nao_existe():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'indicacao', ordem=0)
    _criar_item(checklist, 'como_chegou', ordem=1, condicao={'chave': 'indicacao', 'operador': 'nao_existe', 'valor': None})

    assert [i.chave for i in checklist_service.itens_elegiveis(checklist, {})] == ['indicacao', 'como_chegou']
    assert [i.chave for i in checklist_service.itens_elegiveis(checklist, {'indicacao': 'amigo'})] == ['indicacao']


# ──────────────────────────────────────────────
# proximo_item
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_proximo_item_devolve_primeiro_sem_resposta():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    checklist = _criar_checklist(tenant)
    item_a = _criar_item(checklist, 'nome_completo', ordem=0)
    item_b = _criar_item(checklist, 'cep', ordem=1)

    assert checklist_service.proximo_item(checklist, 'lead', lead.pk).pk == item_a.pk

    checklist_service.registrar_resposta(checklist, item_a, 'lead', lead.pk, 'Fulano de Tal')

    assert checklist_service.proximo_item(checklist, 'lead', lead.pk).pk == item_b.pk


@pytest.mark.django_db
def test_proximo_item_none_quando_tudo_respondido():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    checklist = _criar_checklist(tenant)
    item_a = _criar_item(checklist, 'nome_completo', ordem=0)

    checklist_service.registrar_resposta(checklist, item_a, 'lead', lead.pk, 'Fulano de Tal')

    assert checklist_service.proximo_item(checklist, 'lead', lead.pk) is None


# ──────────────────────────────────────────────
# registrar_resposta
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_registrar_resposta_e_idempotente_e_atualiza_valor():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cep', ordem=0)

    checklist_service.registrar_resposta(checklist, item, 'lead', lead.pk, '64000-000')
    checklist_service.registrar_resposta(checklist, item, 'lead', lead.pk, '64001-000')

    respostas = RespostaChecklist.objects.filter(item=item, entidade_tipo='lead', entidade_id=lead.pk)
    assert respostas.count() == 1
    assert respostas.first().valor == '64001-000'


@pytest.mark.django_db
def test_registrar_resposta_espelha_em_dados_custom_do_lead():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    campo = CampoCustomizado.objects.create(tenant=tenant, entidade='lead', nome='CEP', slug='cep', tipo='texto')
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cep', ordem=0, campo=campo)

    checklist_service.registrar_resposta(checklist, item, 'lead', lead.pk, '64000-000', valor_processado='64000000')

    lead.refresh_from_db()
    assert lead.dados_custom.get('cep') == '64000000'


@pytest.mark.django_db
def test_registrar_resposta_espelha_em_dados_custom_da_oportunidade():
    tenant = TenantFactory()
    estagio = PipelineEstagioFactory(tenant=tenant)
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio)
    campo = CampoCustomizado.objects.create(
        tenant=tenant, entidade='oportunidade', nome='Plano', slug='plano', tipo='texto')
    checklist = _criar_checklist(tenant, entidade_alvo='oportunidade')
    item = _criar_item(checklist, 'plano', ordem=0, campo=campo)

    checklist_service.registrar_resposta(checklist, item, 'oportunidade', op.pk, 'Plano 620')

    op.refresh_from_db()
    assert op.dados_custom.get('plano') == 'Plano 620'


@pytest.mark.django_db
def test_registrar_resposta_sem_campo_nao_mexe_em_dados_custom():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'observacao', ordem=0)  # sem `campo`

    checklist_service.registrar_resposta(checklist, item, 'lead', lead.pk, 'Só um comentário')

    lead.refresh_from_db()
    assert lead.dados_custom == {}


# ──────────────────────────────────────────────
# progresso
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_progresso_conta_so_obrigatorios_elegiveis():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    checklist = _criar_checklist(tenant)
    item_obrigatorio_1 = _criar_item(checklist, 'nome_completo', ordem=0, obrigatorio=True)
    _criar_item(checklist, 'apelido', ordem=1, obrigatorio=False)  # opcional, não conta
    item_obrigatorio_2 = _criar_item(checklist, 'cep', ordem=2, obrigatorio=True)
    _criar_item(
        checklist, 'complemento', ordem=3, obrigatorio=True,
        condicao={'chave': 'tem_numero', 'operador': 'existe', 'valor': None},
    )  # condicional que não bateu, não conta

    progresso = checklist_service.progresso(checklist, 'lead', lead.pk)
    assert progresso == {
        'total': 2, 'respondidos': 0, 'faltando': ['nome_completo', 'cep'],
        'completo': False, 'percentual': 0,
    }

    checklist_service.registrar_resposta(checklist, item_obrigatorio_1, 'lead', lead.pk, 'Fulano de Tal')
    progresso = checklist_service.progresso(checklist, 'lead', lead.pk)
    assert progresso['respondidos'] == 1
    assert progresso['percentual'] == 50
    assert progresso['completo'] is False

    checklist_service.registrar_resposta(checklist, item_obrigatorio_2, 'lead', lead.pk, '64000-000')
    progresso = checklist_service.progresso(checklist, 'lead', lead.pk)
    assert progresso['completo'] is True
    assert progresso['percentual'] == 100
