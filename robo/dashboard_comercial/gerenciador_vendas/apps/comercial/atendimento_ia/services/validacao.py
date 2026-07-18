"""
Cascata de validacao de resposta de UM item do checklist.

Ordem (do mais barato pro mais caro, IA sempre por ultimo e so quando o item
pede `tipo_validacao='ia'` explicitamente): vazio, opcoes, tipo builtin
(email/cpf_cnpj/cep/numero/data), regex, IA.

Conceito copiado de `apps.comercial.atendimento.engine._validar_resposta_questao`
(motor a aposentar), reescrito aqui sem importar de la. Blindado: qualquer
excecao vira resultado, nunca sobe (o Matrix tem timeout de 45s por chamada,
uma view que sobe 500 trava o cliente no meio da conversa).
"""
import json
import logging
import re
import unicodedata
from datetime import datetime

logger = logging.getLogger(__name__)

# Timeout curto: o Matrix corta a chamada HTTP em 45s. A validacao por IA e
# so UM passo de /ia/validar, tem que sobrar tempo pro resto do request.
TIMEOUT_IA_VALIDACAO = 8
MAX_TOKENS_IA_VALIDACAO = 100

PROMPT_SISTEMA_VALIDACAO_IA = (
    'Voce valida a resposta de um cliente numa pergunta de atendimento comercial. '
    'Responda SOMENTE com um JSON, sem markdown e sem texto fora dele, no formato: '
    '{"valida": true ou false, "valor": "resposta normalizada", "motivo": "motivo curto se invalida"}.'
)

_FORMATOS_DATA = ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d')

_MOTIVO_RESPOSTA_VAZIA = 'resposta_vazia'
_MOTIVO_OPCAO_INVALIDA = 'opcao_invalida'
_MOTIVO_EMAIL_INVALIDO = 'email_invalido'
_MOTIVO_CPF_CNPJ_INVALIDO = 'cpf_cnpj_invalido'
_MOTIVO_CEP_INVALIDO = 'cep_invalido'
_MOTIVO_NUMERO_INVALIDO = 'numero_invalido'
_MOTIVO_DATA_INVALIDA = 'data_invalida'
_MOTIVO_FORMATO_INVALIDO = 'formato_invalido'
_MOTIVO_IA_INDISPONIVEL = 'ia_indisponivel'
_MOTIVO_IA_RESPOSTA_INVALIDA = 'ia_resposta_invalida'
_MOTIVO_ERRO_INTERNO = 'erro_interno_validacao'


def _resultado(valida, valor_processado, fonte, erro=''):
    return {'valida': valida, 'valor_processado': valor_processado, 'fonte': fonte, 'erro': erro}


def _normalizar(texto):
    """Minusculo, sem acento, sem espaco nas pontas. Base da comparacao de
    opcoes (o cliente pode responder 'Sao Paulo' pra opcao 'São Paulo')."""
    sem_acento = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    return sem_acento.strip().lower()


def _validar_opcoes(item, resposta_str):
    opcoes = item.opcoes or []

    # Numero da opcao (1-based, e o que o bot mostra na URA).
    if resposta_str.isdigit():
        indice = int(resposta_str)
        if 1 <= indice <= len(opcoes):
            opcao = opcoes[indice - 1]
            valor = opcao.get('valor') if opcao.get('valor') not in (None, '') else opcao.get('texto')
            return _resultado(True, valor, 'opcoes')

    # Texto da opcao (ou o valor interno dela), case/acento insensitive.
    resposta_norm = _normalizar(resposta_str)
    for opcao in opcoes:
        texto_norm = _normalizar(str(opcao.get('texto') or ''))
        valor_norm = _normalizar(str(opcao.get('valor') or ''))
        if resposta_norm and resposta_norm in (texto_norm, valor_norm):
            valor = opcao.get('valor') if opcao.get('valor') not in (None, '') else opcao.get('texto')
            return _resultado(True, valor, 'opcoes')

    return _resultado(False, None, 'opcoes', _MOTIVO_OPCAO_INVALIDA)


_REGEX_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _validar_email(resposta_str):
    if _REGEX_EMAIL.match(resposta_str):
        return _resultado(True, resposta_str.lower(), 'tipo')
    return _resultado(False, None, 'tipo', _MOTIVO_EMAIL_INVALIDO)


def _digito_verificador_cpf(cpf, pesos):
    soma = sum(int(cpf[i]) * pesos[i] for i in range(len(pesos)))
    resto = (soma * 10) % 11
    return 0 if resto == 10 else resto


def _cpf_valido(cpf):
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    dv1 = _digito_verificador_cpf(cpf, range(10, 1, -1))
    if dv1 != int(cpf[9]):
        return False
    dv2 = _digito_verificador_cpf(cpf, range(11, 1, -1))
    return dv2 == int(cpf[10])


def _cnpj_valido(cnpj):
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    dv1 = 0 if resto < 2 else 11 - resto
    if dv1 != int(cnpj[12]):
        return False
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    dv2 = 0 if resto < 2 else 11 - resto
    return dv2 == int(cnpj[13])


def _validar_cpf_cnpj(resposta_str):
    digitos = re.sub(r'\D', '', resposta_str)
    if len(digitos) == 11 and _cpf_valido(digitos):
        return _resultado(True, digitos, 'tipo')
    if len(digitos) == 14 and _cnpj_valido(digitos):
        return _resultado(True, digitos, 'tipo')
    return _resultado(False, None, 'tipo', _MOTIVO_CPF_CNPJ_INVALIDO)


def _validar_cep(resposta_str):
    digitos = re.sub(r'\D', '', resposta_str)
    if len(digitos) == 8:
        return _resultado(True, digitos, 'tipo')
    return _resultado(False, None, 'tipo', _MOTIVO_CEP_INVALIDO)


def _validar_numero(resposta_str):
    try:
        valor = float(resposta_str.replace(',', '.'))
    except ValueError:
        return _resultado(False, None, 'tipo', _MOTIVO_NUMERO_INVALIDO)
    return _resultado(True, valor, 'tipo')


def _validar_data(resposta_str):
    for formato in _FORMATOS_DATA:
        try:
            data = datetime.strptime(resposta_str, formato)
        except ValueError:
            continue
        return _resultado(True, data.strftime('%Y-%m-%d'), 'tipo')
    return _resultado(False, None, 'tipo', _MOTIVO_DATA_INVALIDA)


def _validar_regex(item, resposta_str):
    if not item.regex_validacao:
        # Sem padrao configurado apesar de tipo_validacao='regex': nao trava
        # o cliente por erro de configuracao, aceita como esta.
        return _resultado(True, resposta_str, 'regex')
    try:
        bateu = re.match(item.regex_validacao, resposta_str)
    except re.error:
        logger.warning('Regex invalido no item %s: %s', item.pk, item.regex_validacao)
        return _resultado(True, resposta_str, 'fallback')
    if bateu:
        return _resultado(True, resposta_str, 'regex')
    return _resultado(False, None, 'regex', _MOTIVO_FORMATO_INVALIDO)


def _extrair_json(texto):
    """O LLM as vezes cerca o JSON com markdown mesmo pedindo pra nao. Pega
    o primeiro bloco {...} do texto."""
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    return match.group(0) if match else texto


def _validar_ia(item, resposta_str, tenant):
    from apps.automacao.services.ia import chamar_llm, integracao_ia_do_tenant

    integracao = integracao_ia_do_tenant(tenant)
    if not integracao:
        return _resultado(None, resposta_str, 'fallback', _MOTIVO_IA_INDISPONIVEL)

    mensagens = [
        {'role': 'system', 'content': PROMPT_SISTEMA_VALIDACAO_IA},
        {'role': 'user', 'content': f'Pergunta: {item.pergunta}\nResposta do cliente: {resposta_str}'},
    ]
    # chamar_llm ja blinda erro de rede/HTTP/parse e devolve None: cobre
    # timeout tambem (a lib requests estoura TimeoutError, capturado la dentro).
    texto = chamar_llm(
        integracao, mensagens,
        timeout=TIMEOUT_IA_VALIDACAO, max_tokens=MAX_TOKENS_IA_VALIDACAO,
    )
    if not texto:
        return _resultado(None, resposta_str, 'fallback', _MOTIVO_IA_INDISPONIVEL)

    try:
        dados = json.loads(_extrair_json(texto))
        valida = bool(dados.get('valida'))
        motivo = str(dados.get('motivo') or '')
        if valida:
            valor = dados.get('valor') or resposta_str
            return _resultado(True, valor, 'ia')
        return _resultado(False, None, 'ia', motivo or 'reprovado_pela_ia')
    except (ValueError, TypeError, AttributeError):
        return _resultado(None, resposta_str, 'fallback', _MOTIVO_IA_RESPOSTA_INVALIDA)


def validar(item, resposta, tenant):
    """Valida `resposta` (texto bruto do cliente) contra `item`. Devolve
    sempre um dict {'valida': bool|None, 'valor_processado': any, 'fonte': str,
    'erro': str}. `valida=None` = IA indisponivel, aceita com ressalva.

    Blindado por fora tambem: qualquer excecao inesperada vira resultado
    com fonte='fallback' em vez de subir e derrubar a view."""
    try:
        resposta_str = '' if resposta is None else str(resposta).strip()

        if not resposta_str:
            if item.obrigatorio:
                return _resultado(False, None, '', _MOTIVO_RESPOSTA_VAZIA)
            return _resultado(True, None, '')

        if item.tipo_resposta == 'opcoes':
            return _validar_opcoes(item, resposta_str)

        tipo = item.tipo_validacao
        if tipo == 'email':
            return _validar_email(resposta_str)
        if tipo == 'cpf_cnpj':
            return _validar_cpf_cnpj(resposta_str)
        if tipo == 'cep':
            return _validar_cep(resposta_str)
        if tipo == 'numero':
            return _validar_numero(resposta_str)
        if tipo == 'data':
            return _validar_data(resposta_str)
        if tipo == 'regex':
            return _validar_regex(item, resposta_str)
        if tipo == 'ia':
            return _validar_ia(item, resposta_str, tenant)

        # tipo_validacao='nenhuma': texto livre, aceita como esta.
        return _resultado(True, resposta_str, '')
    except Exception:
        logger.exception('Falha inesperada validando item %s', getattr(item, 'pk', None))
        return _resultado(None, resposta, 'fallback', _MOTIVO_ERRO_INTERNO)
