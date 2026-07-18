"""Simula o loop completo que o bot Matrix roda: /ia/proximo-passo (pergunta)
-> bot renderiza -> captura resposta -> /ia/validar -> volta pro
proximo-passo, ate `proximo_passo == "red_encerrar"`. Cobre os desvios que
importam: resposta valida avanca, invalida repergunta, estouro de tentativas
transborda, item de opcoes aceita numero ou texto, e o ciclo separado de
/ia/recontato (timeout do cliente) encerrando apos 2 tentativas."""
import json

import pytest

from apps.automacao.models import Checklist, ItemChecklist
from apps.comercial.atendimento_ia.models import SessaoAtendimentoBot
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


def _proximo_passo(client, token, cellphone, lead_id=None):
    return _post(client, token, '/ia/proximo-passo', {
        'cellphone': cellphone, 'lead_id': lead_id, 'ultima_mensagem': '',
    }).json()


def _validar(client, token, cellphone, lead_id, question_id, answer):
    return _post(client, token, '/ia/validar', {
        'question': '', 'answer': answer, 'cellphone': cellphone,
        'lead_id': lead_id, 'question_id': question_id,
    }).json()


# ──────────────────────────────────────────────
# resposta valida avanca pro proximo item
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_resposta_valida_avanca_para_o_proximo_item(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'nome_completo', ordem=0)
    _criar_item(checklist, 'cep', ordem=1, tipo_validacao='cep')
    token = _token(tenant)
    cellphone = '5589911110001'

    passo1 = _proximo_passo(client, token, cellphone)
    assert passo1['proximo_passo'] == 'seguir_pergunta'
    lead_id = passo1['lead_id']

    validacao1 = _validar(client, token, cellphone, lead_id, passo1['proxima_pergunta_id'], 'Fulano de Tal')
    assert validacao1['resposta_correta'] is True

    passo2 = _proximo_passo(client, token, cellphone, lead_id)
    assert passo2['proximo_passo'] == 'seguir_pergunta'
    assert passo2['mensagem_inicial'] == 'Pergunta cep?'
    assert passo2['proxima_pergunta_id'] != passo1['proxima_pergunta_id']


@pytest.mark.django_db
def test_checklist_completo_encerra_com_red_encerrar(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'nome_completo', ordem=0)
    token = _token(tenant)
    cellphone = '5589911110002'

    passo1 = _proximo_passo(client, token, cellphone)
    lead_id = passo1['lead_id']
    _validar(client, token, cellphone, lead_id, passo1['proxima_pergunta_id'], 'Fulano de Tal')

    passo2 = _proximo_passo(client, token, cellphone, lead_id)
    assert passo2['proximo_passo'] == 'red_encerrar'
    assert passo2['deve_perguntar'] is False

    sessao = SessaoAtendimentoBot.objects.get(lead_id=lead_id)
    assert sessao.status == 'finalizado'


# ──────────────────────────────────────────────
# resposta invalida repergunta (nao avanca)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_resposta_invalida_repergunta_o_mesmo_item(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(checklist, 'email', ordem=0, tipo_validacao='email', max_tentativas=3)
    token = _token(tenant)
    cellphone = '5589911110003'

    passo1 = _proximo_passo(client, token, cellphone)
    lead_id = passo1['lead_id']
    item_id = passo1['proxima_pergunta_id']

    validacao = _validar(client, token, cellphone, lead_id, item_id, 'nao-eh-email')
    assert validacao['resposta_correta'] is False

    passo2 = _proximo_passo(client, token, cellphone, lead_id)
    # Ainda pede o MESMO item (nao avancou pra outro).
    assert passo2['proxima_pergunta_id'] == item_id
    assert passo2['proximo_passo'] == 'seguir_pergunta'

    sessao = SessaoAtendimentoBot.objects.get(lead_id=lead_id)
    assert sessao.tentativas_item == 1


# ──────────────────────────────────────────────
# estouro de tentativas -> transbordo
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_estouro_de_tentativas_transborda(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(
        checklist, 'email', ordem=0, tipo_validacao='email',
        max_tentativas=2, estrategia_erro='transbordar', mensagem_erro='Email invalido.',
    )
    token = _token(tenant)
    cellphone = '5589911110004'

    passo1 = _proximo_passo(client, token, cellphone)
    lead_id = passo1['lead_id']
    item_id = passo1['proxima_pergunta_id']

    v1 = _validar(client, token, cellphone, lead_id, item_id, 'errado-1')
    assert v1['resposta_correta'] is False
    assert v1['needsReception'] == 'false'

    v2 = _validar(client, token, cellphone, lead_id, item_id, 'errado-2')
    assert v2['resposta_correta'] is False
    # Estourou max_tentativas=2: transborda, needsReception vira "true" (string).
    assert v2['needsReception'] == 'true'
    assert isinstance(v2['needsReception'], str)

    sessao = SessaoAtendimentoBot.objects.get(lead_id=lead_id)
    assert sessao.status == 'transbordado'
    assert sessao.motivo_transbordo == 'max_tentativas_excedida'

    # Idempotente: proximo-passo depois do transbordo so confirma o estado.
    passo2 = _proximo_passo(client, token, cellphone, lead_id)
    assert passo2['deve_transbordar'] == 'true'


@pytest.mark.django_db
def test_estrategia_pular_avanca_mesmo_sem_resposta_valida(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(
        checklist, 'apelido', ordem=0, tipo_validacao='email',
        max_tentativas=1, estrategia_erro='pular',
    )
    _criar_item(checklist, 'cep', ordem=1, tipo_validacao='cep')
    token = _token(tenant)
    cellphone = '5589911110005'

    passo1 = _proximo_passo(client, token, cellphone)
    lead_id = passo1['lead_id']
    item_id = passo1['proxima_pergunta_id']

    v1 = _validar(client, token, cellphone, lead_id, item_id, 'nao-eh-email')
    # max_tentativas=1: essa PRIMEIRA tentativa invalida ja estoura -> pula.
    assert v1['resposta_correta'] is True

    passo2 = _proximo_passo(client, token, cellphone, lead_id)
    assert passo2['mensagem_inicial'] == 'Pergunta cep?'


# ──────────────────────────────────────────────
# item de opcoes aceita numero OU texto
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_item_de_opcoes_aceita_resposta_por_numero(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(
        checklist, 'plano', ordem=0, tipo_resposta='opcoes',
        opcoes=[{'texto': 'Plano 620', 'valor': '620'}, {'texto': 'Plano 1G', 'valor': '1000'}],
    )
    token = _token(tenant)
    cellphone = '5589911110006'

    passo1 = _proximo_passo(client, token, cellphone)
    lead_id = passo1['lead_id']
    item_id = passo1['proxima_pergunta_id']

    validacao = _validar(client, token, cellphone, lead_id, item_id, '2')
    assert validacao['resposta_correta'] is True

    from apps.automacao.models import RespostaChecklist
    resposta = RespostaChecklist.objects.get(item_id=item_id, entidade_tipo='lead', entidade_id=lead_id)
    assert resposta.valor_processado == '1000'


@pytest.mark.django_db
def test_item_de_opcoes_aceita_resposta_por_texto(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    _criar_item(
        checklist, 'plano', ordem=0, tipo_resposta='opcoes',
        opcoes=[{'texto': 'Plano 620', 'valor': '620'}, {'texto': 'Plano 1G', 'valor': '1000'}],
    )
    token = _token(tenant)
    cellphone = '5589911110007'

    passo1 = _proximo_passo(client, token, cellphone)
    lead_id = passo1['lead_id']
    item_id = passo1['proxima_pergunta_id']

    validacao = _validar(client, token, cellphone, lead_id, item_id, 'plano 620')
    assert validacao['resposta_correta'] is True

    from apps.automacao.models import RespostaChecklist
    resposta = RespostaChecklist.objects.get(item_id=item_id, entidade_tipo='lead', entidade_id=lead_id)
    assert resposta.valor_processado == '620'


# ──────────────────────────────────────────────
# timeout do cliente -> /ia/recontato -> encerra apos 2 tentativas
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_recontato_reoergunta_duas_vezes_e_encerra_na_terceira(client):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'nome_completo', ordem=0)
    token = _token(tenant)
    cellphone = '5589911110008'

    passo1 = _proximo_passo(client, token, cellphone)
    lead_id = passo1['lead_id']

    r1 = _post(client, token, '/ia/recontato', {
        'cellphone': cellphone, 'lead_id': lead_id, 'pergunta_id': item.id,
    }).json()
    assert r1['acao'] == 'reperguntar'
    assert r1['tentativa'] == 1
    assert r1['deve_transbordar'] == 'false'

    r2 = _post(client, token, '/ia/recontato', {
        'cellphone': cellphone, 'lead_id': lead_id, 'pergunta_id': item.id,
    }).json()
    assert r2['acao'] == 'reperguntar'
    assert r2['tentativa'] == 2
    assert r2['deve_transbordar'] == 'false'

    r3 = _post(client, token, '/ia/recontato', {
        'cellphone': cellphone, 'lead_id': lead_id, 'pergunta_id': item.id,
    }).json()
    assert r3['acao'] == 'encerrar'
    assert r3['tentativa'] == 3
    assert r3['reperguntar'] is False
    assert r3['deve_transbordar'] == 'true'

    sessao = SessaoAtendimentoBot.objects.get(lead_id=lead_id)
    assert sessao.status == 'transbordado'
    assert sessao.motivo_transbordo == 'recontato_esgotado'
