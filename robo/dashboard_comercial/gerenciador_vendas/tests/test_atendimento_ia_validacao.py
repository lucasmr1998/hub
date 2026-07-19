"""Cascata de validacao (apps.comercial.atendimento_ia.services.validacao):
vazio, opcoes, tipo builtin (email/cpf_cnpj/cep/numero/data), regex, IA.
Sem HTTP: chama `validar(item, resposta, tenant)` direto, como
test_automacao_checklist.py faz pro service da Fase 1."""
from unittest import mock

import pytest

from apps.automacao.models import Checklist, ItemChecklist
from apps.comercial.atendimento_ia.services import validacao, validacao_ia
from tests.factories import TenantFactory


def _criar_checklist(tenant, **kwargs):
    defaults = {'nome': 'Checklist de venda', 'slug': 'checklist-venda', 'contexto': 'bot_vendas'}
    defaults.update(kwargs)
    return Checklist.objects.create(tenant=tenant, **defaults)


def _criar_item(checklist, chave, ordem=0, **kwargs):
    defaults = {'pergunta': f'Pergunta {chave}?', 'ordem': ordem}
    defaults.update(kwargs)
    return ItemChecklist.objects.create(tenant=checklist.tenant, checklist=checklist, chave=chave, **defaults)


# ──────────────────────────────────────────────
# vazio
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_vazio_obrigatorio_invalida():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'nome', obrigatorio=True)

    resultado = validacao.validar(item, '', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'resposta_vazia'


@pytest.mark.django_db
def test_vazio_nao_obrigatorio_valida():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'apelido', obrigatorio=False)

    resultado = validacao.validar(item, None, tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] is None


# ──────────────────────────────────────────────
# opcoes
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_opcoes_aceita_numero_da_opcao():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(
        checklist, 'plano', tipo_resposta='opcoes',
        opcoes=[{'texto': 'Plano 620', 'valor': '620'}, {'texto': 'Plano 1G', 'valor': '1000'}],
    )

    resultado = validacao.validar(item, '2', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == '1000'
    assert resultado['fonte'] == 'opcoes'


@pytest.mark.django_db
def test_opcoes_aceita_texto_com_acento_e_maiuscula_diferente():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(
        checklist, 'cidade', tipo_resposta='opcoes',
        opcoes=[{'texto': 'São Paulo', 'valor': 'SP'}, {'texto': 'Não sei', 'valor': 'indefinido'}],
    )

    resultado = validacao.validar(item, 'sao paulo', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == 'SP'


@pytest.mark.django_db
def test_opcoes_invalida_quando_nao_bate_nada():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(
        checklist, 'plano', tipo_resposta='opcoes',
        opcoes=[{'texto': 'Plano 620', 'valor': '620'}, {'texto': 'Plano 1G', 'valor': '1000'}],
    )

    resultado = validacao.validar(item, 'plano 5G', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'opcao_invalida'


# ──────────────────────────────────────────────
# tipo builtin: email
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_email_valido():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'email', tipo_validacao='email')

    resultado = validacao.validar(item, 'Cliente@Exemplo.com', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == 'cliente@exemplo.com'
    assert resultado['fonte'] == 'tipo'


@pytest.mark.django_db
def test_email_invalido():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'email', tipo_validacao='email')

    resultado = validacao.validar(item, 'nao-eh-email', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'email_invalido'


# ──────────────────────────────────────────────
# tipo builtin: cpf_cnpj (com digito verificador de verdade)
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cpf_valido_com_formatacao():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cpf', tipo_validacao='cpf_cnpj')

    resultado = validacao.validar(item, '111.444.777-35', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == '11144477735'


@pytest.mark.django_db
def test_cpf_com_digito_verificador_errado_invalida():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cpf', tipo_validacao='cpf_cnpj')

    # Mesmos 9 primeiros digitos do CPF valido, digitos verificadores trocados.
    resultado = validacao.validar(item, '111.444.777-99', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'cpf_cnpj_invalido'


@pytest.mark.django_db
def test_cnpj_valido():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cnpj', tipo_validacao='cpf_cnpj')

    resultado = validacao.validar(item, '11.222.333/0001-81', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == '11222333000181'


@pytest.mark.django_db
def test_cpf_todos_digitos_iguais_invalida():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cpf', tipo_validacao='cpf_cnpj')

    resultado = validacao.validar(item, '111.111.111-11', tenant)

    assert resultado['valida'] is False


# ──────────────────────────────────────────────
# tipo builtin: cep
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cep_valido_com_hifen():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cep', tipo_validacao='cep')

    resultado = validacao.validar(item, '64000-000', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == '64000000'


@pytest.mark.django_db
def test_cep_invalido_menos_de_8_digitos():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cep', tipo_validacao='cep')

    resultado = validacao.validar(item, '6400-000', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'cep_invalido'


# ──────────────────────────────────────────────
# tipo builtin: numero
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_numero_valido_com_virgula_decimal():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'valor', tipo_validacao='numero')

    resultado = validacao.validar(item, '99,90', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == 99.90


@pytest.mark.django_db
def test_numero_invalido():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'valor', tipo_validacao='numero')

    resultado = validacao.validar(item, 'nao eh numero', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'numero_invalido'


# ──────────────────────────────────────────────
# tipo builtin: data
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_data_valida_dd_mm_aaaa():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'nascimento', tipo_validacao='data')

    resultado = validacao.validar(item, '15/03/1990', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == '1990-03-15'


@pytest.mark.django_db
def test_data_invalida():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'nascimento', tipo_validacao='data')

    resultado = validacao.validar(item, '31/02/2026', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'data_invalida'


# ──────────────────────────────────────────────
# regex customizado
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_regex_customizado_valido():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(
        checklist, 'protocolo', tipo_validacao='regex', regex_validacao=r'^PROT-\d{4}$',
    )

    resultado = validacao.validar(item, 'PROT-1234', tenant)

    assert resultado['valida'] is True
    assert resultado['fonte'] == 'regex'


@pytest.mark.django_db
def test_regex_customizado_invalido():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(
        checklist, 'protocolo', tipo_validacao='regex', regex_validacao=r'^PROT-\d{4}$',
    )

    resultado = validacao.validar(item, 'abc', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'formato_invalido'


# ──────────────────────────────────────────────
# IA (mockada: nao bate rede de verdade)
# ──────────────────────────────────────────────

@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_ia_aprova_resposta(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo_cancelamento', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = (
        '{"valido": true, "dados_extraidos": "quer trocar de operadora", "mensagem_bot": "", '
        '"motivo_invalido": "", "confianca": 0.9, "intencao_detectada": "ok"}'
    )

    resultado = validacao.validar(item, 'quero trocar de operadora', tenant)

    assert resultado['valida'] is True
    assert resultado['valor_processado'] == 'quer trocar de operadora'
    assert resultado['fonte'] == 'ia'
    # timeout curto e proposital: e o unico passo de IA dentro do orcamento de 45s do Matrix.
    assert mock_chamar_llm.call_args.kwargs['timeout'] == validacao_ia._TIMEOUT_IA


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_ia_reprova_resposta(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo_cancelamento', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = (
        '{"valido": false, "dados_extraidos": {}, "mensagem_bot": "resposta fora de contexto", '
        '"motivo_invalido": "fora_de_contexto", "confianca": 0.9, "intencao_detectada": "ok"}'
    )

    resultado = validacao.validar(item, 'blablabla', tenant)

    assert resultado['valida'] is False
    assert resultado['erro'] == 'resposta fora de contexto'
    assert resultado['fonte'] == 'ia'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_ia_timeout_cai_em_fallback_valida_none(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo_cancelamento', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    # chamar_llm ja blinda timeout/erro de rede e devolve None (contrato do
    # servico em apps/automacao/services/ia.py).
    mock_chamar_llm.return_value = None

    resultado = validacao.validar(item, 'qualquer coisa', tenant)

    assert resultado['valida'] is None
    assert resultado['fonte'] == 'fallback'
    assert resultado['erro'] == 'ia_indisponivel'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_ia_sem_integracao_ativa_cai_em_fallback(mock_integracao):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo_cancelamento', tipo_validacao='ia')
    mock_integracao.return_value = None

    resultado = validacao.validar(item, 'qualquer coisa', tenant)

    assert resultado['valida'] is None
    assert resultado['fonte'] == 'fallback'


@pytest.mark.django_db
@mock.patch('apps.automacao.services.ia.chamar_llm')
@mock.patch('apps.automacao.services.ia.integracao_ia_do_tenant')
def test_ia_json_invalido_cai_em_fallback(mock_integracao, mock_chamar_llm):
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'motivo_cancelamento', tipo_validacao='ia')
    mock_integracao.return_value = mock.Mock()
    mock_chamar_llm.return_value = 'isso aqui nao e JSON nenhum'

    resultado = validacao.validar(item, 'qualquer coisa', tenant)

    assert resultado['valida'] is None
    assert resultado['fonte'] == 'fallback'
    assert resultado['erro'] == 'ia_resposta_invalida'


# ──────────────────────────────────────────────
# blindagem: excecao inesperada nunca sobe
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_excecao_inesperada_vira_fallback_em_vez_de_subir():
    tenant = TenantFactory()
    checklist = _criar_checklist(tenant)
    item = _criar_item(checklist, 'cep', tipo_validacao='cep')

    with mock.patch('apps.comercial.atendimento_ia.services.validacao._validar_cep', side_effect=RuntimeError('boom')):
        resultado = validacao.validar(item, '64000-000', tenant)

    assert resultado['valida'] is None
    assert resultado['fonte'] == 'fallback'
    assert resultado['erro'] == 'erro_interno_validacao'
