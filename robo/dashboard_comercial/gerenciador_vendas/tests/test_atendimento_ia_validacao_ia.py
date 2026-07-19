"""Validacao por IA (apps.comercial.atendimento_ia.services.validacao_ia) e a
integracao dela na cascata (services/validacao.py) e no endpoint /ia/validar.

LLM SEMPRE mockado (`apps.automacao.services.ia.chamar_llm` /
`integracao_ia_do_tenant`): nenhum teste aqui bate API de verdade."""
import json
from unittest import mock

import pytest

from apps.automacao.models import Checklist, ItemChecklist
from apps.comercial.atendimento_ia.models import SessaoAtendimentoBot
from apps.comercial.atendimento_ia.services import validacao, validacao_ia
from apps.integracoes.models import IntegracaoAPI
from tests.factories import TenantFactory


def _criar_checklist(tenant, **kwargs):
    defaults = {'nome': 'Checklist de venda', 'slug': 'checklist-venda', 'contexto': 'bot_vendas'}
    defaults.update(kwargs)
    return Checklist.objects.create(tenant=tenant, **defaults)


def _criar_item(checklist, chave, ordem=0, **kwargs):
    defaults = {'pergunta': f'Pergunta {chave}?', 'ordem': ordem}
    defaults.update(kwargs)
    return ItemChecklist.objects.create(tenant=checklist.tenant, checklist=checklist, chave=chave, **defaults)


def _json_llm(**overrides):
    """Payload JSON valido no contrato novo, com defaults sensatos; cada
    teste sobrescreve so o que importa pro cenario."""
    dados = {
        'valido': True, 'dados_extraidos': '', 'mensagem_bot': '',
        'motivo_invalido': '', 'confianca': 0.9, 'intencao_detectada': 'ok',
    }
    dados.update(overrides)
    return json.dumps(dados)


# ──────────────────────────────────────────────
# validar_com_ia — contrato JSON
# ──────────────────────────────────────────────

@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_json_valido_extrai_valor_de_dados_extraidos(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = _json_llm(dados_extraidos='quer trocar de operadora')

    resultado = validacao_ia.validar_com_ia(item, 'quero trocar de operadora', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == 'quer trocar de operadora'
    assert resultado['fonte'] == 'ia'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_json_invalido_erro_igual_mensagem_bot(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = _json_llm(
        valido=False, mensagem_bot='Nao entendi, pode explicar melhor? 🙂',
        motivo_invalido='fora_de_contexto',
    )

    resultado = validacao_ia.validar_com_ia(item, 'blablabla', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'Nao entendi, pode explicar melhor? 🙂'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_confianca_abaixo_do_minimo_trata_como_invalida(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    assert validacao_ia._CONFIANCA_MINIMA == 0.6  # limiar documentado
    mock_chamar_llm.return_value = _json_llm(valido=True, dados_extraidos='talvez', confianca=0.3)

    resultado = validacao_ia.validar_com_ia(item, 'sei la', tenant)

    assert resultado['valida'] is False
    assert resultado['confianca'] == 0.3


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_intencao_desistir_propaga(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = _json_llm(
        valido=False, mensagem_bot='Tudo bem, vou te transferir.', intencao_detectada='desistir',
    )

    resultado = validacao_ia.validar_com_ia(item, 'nao quero mais, cancela', tenant)

    assert resultado['intencao'] == 'desistir'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_json_com_cerca_de_codigo_parseia_mesmo_assim(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = '```json\n' + _json_llm(dados_extraidos='ok') + '\n```'

    resultado = validacao_ia.validar_com_ia(item, 'resposta qualquer', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == 'ok'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_texto_que_nao_e_json_cai_em_fallback_sem_levantar(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = 'desculpa, nao consigo ajudar com isso'

    resultado = validacao_ia.validar_com_ia(item, 'qualquer coisa', tenant)

    assert resultado['valida'] is None
    assert resultado['fonte'] == 'fallback'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_llm_levanta_excecao_cai_em_fallback_sem_levantar(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.side_effect = TimeoutError('boom')

    resultado = validacao_ia.validar_com_ia(item, 'qualquer coisa', tenant)

    assert resultado['valida'] is None
    assert resultado['fonte'] == 'fallback'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_tenant_sem_integracao_de_ia_cai_em_fallback_sem_levantar(mock_integracao):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo', tipo_validacao='ia')
    mock_integracao.return_value = None

    resultado = validacao_ia.validar_com_ia(item, 'qualquer coisa', tenant)

    assert resultado['valida'] is None
    assert resultado['fonte'] == 'fallback'


# ──────────────────────────────────────────────
# segunda opiniao (cascata: services/validacao.py)
# ──────────────────────────────────────────────

@pytest.mark.django_db
@mock.patch('apps.comercial.atendimento_ia.services.validacao_ia.validar_com_ia')
def test_deterministica_falha_com_instrucoes_ia_tenta_segunda_opiniao(mock_validar_ia):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(
        checklist, 'nome', tipo_validacao='regex', regex_validacao=r'^[A-Z][a-z]+ [A-Z][a-z]+$',
        instrucoes_ia='Aceite qualquer nome de pessoa, mesmo com 3 ou mais palavras.',
    )
    mock_validar_ia.return_value = {
        'valida': True, 'valor_processado': 'joao silva ribeiro', 'fonte': 'ia', 'erro': '',
        'confianca': 0.95, 'intencao': 'ok', 'mensagem_bot': '',
    }

    # "joao silva ribeiro" nao bate o regex rigido (2 palavras, maiuscula inicial).
    resultado = validacao.validar(item, 'joao silva ribeiro', tenant)

    mock_validar_ia.assert_called_once()
    assert resultado['valida'] is True
    assert resultado['valor_processado'] == 'joao silva ribeiro'
    assert resultado['fonte'] == 'ia_segunda_opiniao'


@pytest.mark.django_db
@mock.patch('apps.comercial.atendimento_ia.services.validacao_ia.validar_com_ia')
def test_deterministica_falha_sem_instrucoes_ia_nao_chama_ia(mock_validar_ia):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'email', tipo_validacao='email')  # sem instrucoes_ia

    resultado = validacao.validar(item, 'nao-eh-email', tenant)

    mock_validar_ia.assert_not_called()
    assert resultado['valida'] is False
    assert resultado['fonte'] == 'tipo'
    assert resultado['erro'] == 'email_invalido'


# ──────────────────────────────────────────────
# endpoint /ia/validar — intencao de desistir transborda
# ──────────────────────────────────────────────

def _token(tenant):
    integracao = IntegracaoAPI.objects.create(
        tenant=tenant, nome='Matrix', tipo='outro', api_token='token-matrix-teste-ia', ativa=True,
    )
    return integracao.api_token


def _post(client, token, path, payload):
    return client.post(
        path, data=json.dumps(payload), content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {token}',
    )


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_endpoint_validar_intencao_desistir_transborda(mock_integracao, mock_chamar_llm, client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'motivo_cancelamento', tipo_validacao='ia')
    token = _token(tenant)
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = _json_llm(
        valido=False, mensagem_bot='Sem problemas, vou te passar pra um atendente.',
        intencao_detectada='desistir',
    )

    r1 = _post(client, token, '/ia/proximo-passo', {'cellphone': '5589999991111', 'lead_id': None})
    lead_id = r1.json()['lead_id']

    r = _post(client, token, '/ia/validar', {
        'question': 'Qual o motivo?', 'answer': 'nao quero mais, pode cancelar',
        'cellphone': '5589999991111', 'lead_id': lead_id, 'question_id': r1.json()['proxima_pergunta_id'],
    })

    assert r.status_code == 200, r.content
    data = r.json()
    # needsReception e STRING "true"/"false" (contrato imutavel com o Matrix).
    assert isinstance(data['needsReception'], str)
    assert data['needsReception'] == 'true'

    sessao = SessaoAtendimentoBot.objects.get(tenant=tenant, cellphone='5589999991111')
    assert sessao.status == 'transbordado'
    assert sessao.motivo_transbordo == 'desistir'
