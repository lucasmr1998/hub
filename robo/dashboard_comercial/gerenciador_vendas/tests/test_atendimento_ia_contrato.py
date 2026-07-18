"""Contrato IMUTAVEL com o Matrix: as 3 respostas HTTP tem que ter EXATAMENTE
as chaves esperadas, e cada chave tem que ter o TIPO Python exato da tabela
da tarefa (ver services/contrato.py). Mismatch de tipo nao gera erro nenhum
no bot: so faz ele cair na branch errada, em silencio. Esse eh o teste mais
importante da Fase 2."""
import json
from types import SimpleNamespace

import pytest

from apps.automacao.models import Checklist, ItemChecklist
from apps.comercial.atendimento_ia.services.contrato import ura
from apps.integracoes.models import IntegracaoAPI
from tests.factories import TenantFactory

CHAVES_PROXIMO_PASSO = {
    'lead_id', 'status_lead', 'proximo_passo', 'proxima_pergunta_id',
    'deve_perguntar', 'deve_transbordar', 'motivo', 'intent_detectado',
    'mensagem_inicial', 'ura',
}
CHAVES_URA = {'total_opcoes', 'titulo', 'opcoes', 'pergunta'}
CHAVES_VALIDAR = {
    'resposta_correta', 'resposta_sem_erro_api', 'retorno_erro_api',
    'needsReception', 'isAClient', 'cancelado', 'message',
}
CHAVES_RECONTATO = {'pergunta_id', 'acao', 'tentativa', 'reperguntar', 'mensagem', 'deve_transbordar'}


def _criar_checklist(tenant, **kwargs):
    defaults = {'nome': 'Checklist de venda', 'slug': 'checklist-venda', 'contexto': 'bot_vendas'}
    defaults.update(kwargs)
    return Checklist.objects.create(tenant=tenant, **defaults)


def _criar_item(checklist, chave, ordem=0, **kwargs):
    defaults = {'pergunta': f'Pergunta {chave}?', 'ordem': ordem}
    defaults.update(kwargs)
    return ItemChecklist.objects.create(tenant=checklist.tenant, checklist=checklist, chave=chave, **defaults)


def _token(tenant):
    integracao = IntegracaoAPI.objects.create(
        tenant=tenant, nome='Matrix', tipo='outro', api_token='token-matrix-teste', ativa=True,
    )
    return integracao.api_token


def _post(client, token, path, payload):
    return client.post(
        path, data=json.dumps(payload), content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {token}',
    )


# ──────────────────────────────────────────────
# ura() isolado (sem HTTP): garante que 1 ou 6+ opcoes nunca aparecem
# ──────────────────────────────────────────────

def test_ura_item_texto_livre_devolve_total_opcoes_zero():
    item = SimpleNamespace(tipo_resposta='texto_livre', opcoes=[], ura_titulo='', pergunta='Qual seu nome?')
    resultado = ura(item)
    assert resultado['total_opcoes'] == 0
    assert resultado == {'total_opcoes': 0, 'titulo': '', 'opcoes': [], 'pergunta': ''}


def test_ura_com_1_opcao_cai_no_default_zero():
    item = SimpleNamespace(tipo_resposta='opcoes', opcoes=[{'texto': 'Unica'}], ura_titulo='', pergunta='?')
    assert ura(item)['total_opcoes'] == 0


def test_ura_com_6_opcoes_cai_no_default_zero():
    opcoes = [{'texto': f'Opcao {i}'} for i in range(6)]
    item = SimpleNamespace(tipo_resposta='opcoes', opcoes=opcoes, ura_titulo='', pergunta='?')
    assert ura(item)['total_opcoes'] == 0


@pytest.mark.parametrize('quantidade', [2, 3, 4, 5])
def test_ura_com_2_a_5_opcoes_reconhece(quantidade):
    opcoes = [{'texto': f'Opcao {i}', 'valor': str(i)} for i in range(quantidade)]
    item = SimpleNamespace(tipo_resposta='opcoes', opcoes=opcoes, ura_titulo='menu', pergunta='Qual?')
    resultado = ura(item)
    assert resultado['total_opcoes'] == quantidade
    assert resultado['opcoes'] == [{'texto': f'Opcao {i}'} for i in range(quantidade)]
    assert resultado['titulo'] == 'menu'
    assert resultado['pergunta'] == 'Qual?'


def test_ura_item_none():
    assert ura(None) == {'total_opcoes': 0, 'titulo': '', 'opcoes': [], 'pergunta': ''}


# ──────────────────────────────────────────────
# /ia/proximo-passo
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_proximo_passo_chaves_e_tipos_exatos(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'nome_completo', ordem=0)
    token = _token(tenant)

    r = _post(client, token, '/ia/proximo-passo', {
        'cellphone': '5589999990001', 'lead_id': None, 'ultima_mensagem': '',
    })

    assert r.status_code == 200, r.content
    data = r.json()

    assert set(data.keys()) == CHAVES_PROXIMO_PASSO, data.keys()
    assert set(data['ura'].keys()) == CHAVES_URA

    assert isinstance(data['lead_id'], int) and not isinstance(data['lead_id'], bool)
    assert data['lead_id'] > 0  # lead minimo foi criado

    # status_lead POLIMORFICO: sessao nova = int 0 (nao string "0").
    assert data['status_lead'] == 0
    assert isinstance(data['status_lead'], int) and not isinstance(data['status_lead'], bool)

    assert isinstance(data['proximo_passo'], str)
    assert data['proximo_passo'] == 'seguir_pergunta'

    assert isinstance(data['proxima_pergunta_id'], int) and not isinstance(data['proxima_pergunta_id'], bool)
    assert data['proxima_pergunta_id'] > 0

    assert isinstance(data['deve_perguntar'], bool)
    assert data['deve_perguntar'] is True

    # deve_transbordar e STRING "true"/"false", NAO bool.
    assert isinstance(data['deve_transbordar'], str)
    assert data['deve_transbordar'] == 'false'

    assert isinstance(data['motivo'], str)
    assert isinstance(data['intent_detectado'], str)
    assert isinstance(data['mensagem_inicial'], str)
    assert data['mensagem_inicial'] == 'Pergunta nome_completo?'

    assert isinstance(data['ura'], dict)
    assert isinstance(data['ura']['total_opcoes'], int) and not isinstance(data['ura']['total_opcoes'], bool)
    assert data['ura']['total_opcoes'] == 0  # item texto_livre
    assert isinstance(data['ura']['titulo'], str)
    assert isinstance(data['ura']['opcoes'], list)
    assert isinstance(data['ura']['pergunta'], str)


@pytest.mark.django_db
def test_proximo_passo_com_item_de_opcoes_preenche_ura(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(
        checklist, 'plano', ordem=0, tipo_resposta='opcoes',
        opcoes=[{'texto': 'Plano 620', 'valor': '620'}, {'texto': 'Plano 1G', 'valor': '1000'}],
        ura_titulo='confirmacao_plano_620',
    )
    token = _token(tenant)

    r = _post(client, token, '/ia/proximo-passo', {'cellphone': '5589999990002', 'lead_id': None})

    data = r.json()
    assert data['ura']['total_opcoes'] == 2
    assert not isinstance(data['ura']['total_opcoes'], bool)
    assert data['ura']['opcoes'] == [{'texto': 'Plano 620'}, {'texto': 'Plano 1G'}]
    assert data['ura']['titulo'] == 'confirmacao_plano_620'


@pytest.mark.django_db
def test_proximo_passo_sem_checklist_transborda_com_tipos_corretos(client):
    tenant = TenantFactory()  # sem checklist nenhum
    token = _token(tenant)

    r = _post(client, token, '/ia/proximo-passo', {'cellphone': '5589999990003', 'lead_id': None})

    data = r.json()
    assert set(data.keys()) == CHAVES_PROXIMO_PASSO
    assert data['deve_transbordar'] == 'true'
    assert isinstance(data['deve_transbordar'], str)
    assert data['motivo'] == 'sem_checklist'
    assert isinstance(data['lead_id'], int)
    assert isinstance(data['proxima_pergunta_id'], int)


# ──────────────────────────────────────────────
# /ia/validar
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_validar_chaves_e_tipos_exatos_resposta_valida(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'nome_completo', ordem=0)
    token = _token(tenant)

    r1 = _post(client, token, '/ia/proximo-passo', {'cellphone': '5589999990004', 'lead_id': None})
    lead_id = r1.json()['lead_id']

    r = _post(client, token, '/ia/validar', {
        'question': item.pergunta, 'answer': 'Fulano de Tal',
        'cellphone': '5589999990004', 'lead_id': lead_id, 'question_id': item.id,
    })

    assert r.status_code == 200, r.content
    data = r.json()
    assert set(data.keys()) == CHAVES_VALIDAR, data.keys()

    assert isinstance(data['resposta_correta'], bool) and not isinstance(data['resposta_correta'], str)
    assert data['resposta_correta'] is True

    assert isinstance(data['resposta_sem_erro_api'], bool)

    assert isinstance(data['retorno_erro_api'], str)

    # needsReception e STRING "true"/"false", NAO bool.
    assert isinstance(data['needsReception'], str)
    assert data['needsReception'] == 'false'

    assert isinstance(data['isAClient'], bool)
    assert isinstance(data['cancelado'], bool)
    assert isinstance(data['message'], str)


@pytest.mark.django_db
def test_validar_chaves_e_tipos_exatos_resposta_invalida(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'email', ordem=0, tipo_validacao='email', mensagem_erro='Manda um email valido.')
    token = _token(tenant)

    r1 = _post(client, token, '/ia/proximo-passo', {'cellphone': '5589999990005', 'lead_id': None})
    lead_id = r1.json()['lead_id']
    item_id = r1.json()['proxima_pergunta_id']

    r = _post(client, token, '/ia/validar', {
        'question': 'Qual seu email?', 'answer': 'nao-eh-email',
        'cellphone': '5589999990005', 'lead_id': lead_id, 'question_id': item_id,
    })

    data = r.json()
    assert set(data.keys()) == CHAVES_VALIDAR
    assert data['resposta_correta'] is False
    assert isinstance(data['resposta_correta'], bool)
    assert data['retorno_erro_api'] == 'Manda um email valido.'
    assert isinstance(data['needsReception'], str) and data['needsReception'] in ('true', 'false')


# ──────────────────────────────────────────────
# /ia/recontato
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_recontato_chaves_e_tipos_exatos(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'nome_completo', ordem=0)
    token = _token(tenant)

    r1 = _post(client, token, '/ia/proximo-passo', {'cellphone': '5589999990006', 'lead_id': None})
    lead_id = r1.json()['lead_id']

    r = _post(client, token, '/ia/recontato', {
        'cellphone': '5589999990006', 'lead_id': lead_id, 'pergunta_id': item.id,
    })

    assert r.status_code == 200, r.content
    data = r.json()
    assert set(data.keys()) == CHAVES_RECONTATO, data.keys()

    assert isinstance(data['pergunta_id'], int) and not isinstance(data['pergunta_id'], bool)
    assert isinstance(data['acao'], str)
    assert isinstance(data['tentativa'], int) and not isinstance(data['tentativa'], bool)
    assert data['tentativa'] == 1
    assert isinstance(data['reperguntar'], bool)
    assert data['reperguntar'] is True
    assert isinstance(data['mensagem'], str)

    # deve_transbordar e STRING "true"/"false", NAO bool.
    assert isinstance(data['deve_transbordar'], str)
    assert data['deve_transbordar'] == 'false'
