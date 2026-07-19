"""
Cascata de validacao de resposta de UM item do checklist.

Ordem (do mais barato pro mais caro): vazio, opcoes, tipo builtin
(email/cpf_cnpj/cep/numero/data), regex, IA (services/validacao_ia.py).

A IA entra de DUAS formas:
1. PRIMARIA: item com `tipo_validacao='ia'` — so tem julgamento livre, sempre
   chama a IA (nao ha deterministico pra tentar antes).
2. SEGUNDA OPINIAO: qualquer validacao deterministica (opcoes/tipo/regex) que
   FALHOU, quando o item tem `instrucoes_ia` preenchida — cobre o caso de um
   extractor rigido demais recusar uma resposta que um humano aceitaria (ex:
   cliente respondeu "joao silva ribeiro" e um regex mal calibrado recusou).
   Sem `instrucoes_ia` configurada, uma reprovacao NUNCA aciona a IA (nao
   gasta token a toa) — ver `_com_segunda_opiniao_ia`.

Conceito copiado de `apps.comercial.atendimento.engine._validar_resposta_questao`
(motor a aposentar), reescrito aqui sem importar de la. Blindado: qualquer
excecao vira resultado, nunca sobe (o Matrix tem timeout de 45s por chamada,
uma view que sobe 500 trava o cliente no meio da conversa).
"""
import logging
import re
import unicodedata
from datetime import datetime

from . import validacao_ia

logger = logging.getLogger(__name__)

# Intencoes que fazem /ia/validar transbordar pra humano em vez de insistir
# na pergunta, mesmo quando a resposta em si validou (consumido em
# apps/comercial/atendimento_ia/views.py::validar).
INTENCOES_TRANSBORDO = frozenset({validacao_ia.INTENCAO_DESISTIR, validacao_ia.INTENCAO_TRANSFERIR_HUMANO})

_FORMATOS_DATA = ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d')

_MOTIVO_RESPOSTA_VAZIA = 'resposta_vazia'
_MOTIVO_OPCAO_INVALIDA = 'opcao_invalida'
_MOTIVO_EMAIL_INVALIDO = 'email_invalido'
_MOTIVO_CPF_CNPJ_INVALIDO = 'cpf_cnpj_invalido'
_MOTIVO_CEP_INVALIDO = 'cep_invalido'
_MOTIVO_NUMERO_INVALIDO = 'numero_invalido'
_MOTIVO_DATA_INVALIDA = 'data_invalida'
_MOTIVO_FORMATO_INVALIDO = 'formato_invalido'
_MOTIVO_ERRO_INTERNO = 'erro_interno_validacao'


def _resultado(valida, valor_processado, fonte, erro='', confianca=None, intencao=''):
    """`confianca`/`intencao` sao opcionais e so vem preenchidos quando a
    fonte passou pela IA (primaria ou segunda opiniao) — nas fontes
    deterministicas ficam None/'' (campos novos, nao quebram quem so olha
    valida/valor_processado/fonte/erro)."""
    return {
        'valida': valida, 'valor_processado': valor_processado, 'fonte': fonte, 'erro': erro,
        'confianca': confianca, 'intencao': intencao,
    }


def _resultado_de_ia(resultado_ia, fonte=None):
    """Traduz o dict de `validacao_ia.validar_com_ia` (7 chaves) pro shape da
    cascata. `erro` ja vem como a mensagem humanizada quando invalida (ver
    contrato de `validacao_ia._resultado`)."""
    return _resultado(
        resultado_ia['valida'], resultado_ia['valor_processado'], fonte or resultado_ia['fonte'],
        resultado_ia['erro'], resultado_ia['confianca'], resultado_ia['intencao'],
    )


def _com_segunda_opiniao_ia(item, resposta_str, tenant, resultado):
    """Segunda opiniao (ver docstring do modulo): so aciona quando o
    resultado deterministico reprovou (`valida is False`) E o item tem
    `instrucoes_ia` preenchida. Se a IA confirmar validez, essa vira a
    resposta final; se nao confirmar (invalida ou fallback), mantem a
    reprovacao deterministica original — so repassa a `intencao` se a IA
    detectou uma relevante (ex: cliente "desistiu" no meio de uma resposta
    invalida)."""
    if resultado['valida'] is not False or not item.instrucoes_ia:
        return resultado

    resultado_ia = validacao_ia.validar_com_ia(item, resposta_str, tenant)
    if resultado_ia['valida'] is True:
        return _resultado_de_ia(resultado_ia, fonte='ia_segunda_opiniao')

    if resultado_ia['intencao'] in INTENCOES_TRANSBORDO:
        resultado = dict(resultado, intencao=resultado_ia['intencao'])
    return resultado


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


def validar(item, resposta, tenant):
    """Valida `resposta` (texto bruto do cliente) contra `item`. Devolve
    sempre um dict {'valida': bool|None, 'valor_processado': any, 'fonte': str,
    'erro': str, 'confianca': float|None, 'intencao': str}. `valida=None` =
    IA indisponivel, aceita com ressalva.

    Blindado por fora tambem: qualquer excecao inesperada vira resultado
    com fonte='fallback' em vez de subir e derrubar a view."""
    try:
        resposta_str = '' if resposta is None else str(resposta).strip()

        if not resposta_str:
            if item.obrigatorio:
                return _resultado(False, None, '', _MOTIVO_RESPOSTA_VAZIA)
            return _resultado(True, None, '')

        if item.tipo_resposta == 'opcoes':
            resultado = _validar_opcoes(item, resposta_str)
            return _com_segunda_opiniao_ia(item, resposta_str, tenant, resultado)

        tipo = item.tipo_validacao
        if tipo == 'ia':
            # IA e a validacao PRIMARIA do item (nao segunda opiniao): sempre
            # chama, e o unico jeito de validar esse item.
            return _resultado_de_ia(validacao_ia.validar_com_ia(item, resposta_str, tenant))
        if tipo == 'email':
            resultado = _validar_email(resposta_str)
        elif tipo == 'cpf_cnpj':
            resultado = _validar_cpf_cnpj(resposta_str)
        elif tipo == 'cep':
            resultado = _validar_cep(resposta_str)
        elif tipo == 'numero':
            resultado = _validar_numero(resposta_str)
        elif tipo == 'data':
            resultado = _validar_data(resposta_str)
        elif tipo == 'regex':
            resultado = _validar_regex(item, resposta_str)
        else:
            # tipo_validacao='nenhuma': texto livre, aceita como esta. Nao ha
            # o que questionar aqui, entao nao passa pela segunda opiniao.
            return _resultado(True, resposta_str, '')

        return _com_segunda_opiniao_ia(item, resposta_str, tenant, resultado)
    except Exception:
        logger.exception('Falha inesperada validando item %s', getattr(item, 'pk', None))
        return _resultado(None, resposta, 'fallback', _MOTIVO_ERRO_INTERNO)
