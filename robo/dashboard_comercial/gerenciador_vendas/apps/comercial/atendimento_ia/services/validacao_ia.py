"""
Validacao por IA de UMA resposta de item do checklist. Modulo separado e
testavel (ver tests/test_atendimento_ia_validacao_ia.py), chamado pela
cascata em `services/validacao.py` de duas formas: como validacao PRIMARIA
(item com `tipo_validacao='ia'`) ou como SEGUNDA OPINIAO (validacao
deterministica falhou e o item tem `instrucoes_ia` preenchida).

Tecnicas copiadas do robo de atendimento que ja roda em producao:
1. IA e ULTIMO recurso — quem decide chamar ou nao e o `validacao.py`, este
   modulo so executa quando mandado.
2. Contrato JSON forcado com 6 campos, incluindo `intencao_detectada`: da pro
   fluxo reagir a desistencia/pedido de humano em vez de insistir na
   pergunta (ver `apps/comercial/atendimento_ia/views.py::validar`).
3. Fallback gracioso: timeout, erro HTTP, JSON invalido ou tenant sem
   integracao de IA NUNCA levantam excecao, sempre devolvem
   `valida=None` (aceito com ressalva, mesmo contrato da cascata
   deterministica).
4. `max_tokens` baixo e prompt curto: e validacao, nao conversa.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

# Timeout curto: e so um passo dentro do orcamento de 45s por chamada que o
# Matrix aplica. 8s deixa sobrar tempo pro resto do request de /ia/validar.
_TIMEOUT_IA = 8
# Validacao, nao conversa: prompt curto, resposta e um JSON de poucos campos.
_MAX_TOKENS = 400
# Abaixo disso a IA disse "valido" mas sem certeza suficiente pra confiar o
# dado no CRM sem revisao — trata como invalida em vez de arriscar.
_CONFIANCA_MINIMA = 0.6

INTENCAO_OK = 'ok'
INTENCAO_DUVIDA = 'duvida'
INTENCAO_DESISTIR = 'desistir'
INTENCAO_TRANSFERIR_HUMANO = 'transferir_humano'
_INTENCOES_VALIDAS = frozenset({INTENCAO_OK, INTENCAO_DUVIDA, INTENCAO_DESISTIR, INTENCAO_TRANSFERIR_HUMANO})
_INTENCAO_PADRAO = INTENCAO_OK

_MOTIVO_IA_INDISPONIVEL = 'ia_indisponivel'
_MOTIVO_IA_RESPOSTA_INVALIDA = 'ia_resposta_invalida'
_MOTIVO_IA_CONFIANCA_BAIXA = 'confianca_baixa'
_MOTIVO_IA_REPROVADO = 'reprovado_pela_ia'

# Placeholder resolvido em `_montar_mensagens` pro nome real do tenant. Nunca
# hardcodar nome de empresa aqui: o prompt e compartilhado por todos os tenants.
_PLACEHOLDER_EMPRESA = '{{empresa}}'

PROMPT_SISTEMA = (
    f'Voce e um atendente humano de um provedor de internet chamado {_PLACEHOLDER_EMPRESA}. '
    'Tom cordial e direto, como quem atende WhatsApp de verdade. Nunca revele que e uma IA.\n\n'
    'Sua tarefa e validar se a resposta do cliente serve pra pergunta feita. '
    'Responda SEMPRE e SOMENTE com um JSON valido, sem markdown, sem texto antes ou depois, '
    'no formato exato:\n'
    '{"valido": true ou false, "dados_extraidos": {}, "mensagem_bot": "", '
    '"motivo_invalido": "", "confianca": 0.0 a 1.0, "intencao_detectada": ""}\n\n'
    'Regras:\n'
    'valido = false quando a resposta nao serve pra pergunta (fora de contexto, incompleta, '
    'ambigua ou claramente errada).\n'
    'dados_extraidos: o dado que a pergunta pedia, ja normalizado (ex: nome, motivo, endereco). '
    'Vazio quando invalido.\n'
    'mensagem_bot: quando invalido, peca a informacao de novo de forma gentil e curta '
    '(1 a 2 frases, no maximo 1 emoji). Quando valido pode ficar vazio.\n'
    'motivo_invalido: motivo curto, poucas palavras, so quando invalido.\n'
    'confianca: o quanto voce tem certeza do julgamento, de 0.0 a 1.0.\n'
    'intencao_detectada: um destes valores. ok (resposta normal), duvida (cliente perguntou '
    'algo em vez de responder), desistir (cliente quer parar ou cancelar o atendimento), '
    'transferir_humano (cliente pede pra falar com atendente).'
)


def _extrair_json(texto):
    """O LLM as vezes cerca o JSON com cerca de codigo (```json ... ```) mesmo
    pedindo pra nao. Pega o primeiro bloco {...} do texto, cercado ou nao."""
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    return match.group(0) if match else texto


def _resultado(valida, valor_processado, fonte, erro='', confianca=0.0, intencao=_INTENCAO_PADRAO, mensagem_bot=''):
    return {
        'valida': valida,
        'valor_processado': valor_processado,
        'fonte': fonte,
        'erro': erro,
        'confianca': confianca,
        'intencao': intencao,
        'mensagem_bot': mensagem_bot,
    }


def _montar_mensagens(item, resposta_str, tenant, contexto_coletado):
    nome_tenant = getattr(tenant, 'nome', '') or 'a empresa'
    persona = PROMPT_SISTEMA.replace(_PLACEHOLDER_EMPRESA, nome_tenant)

    partes = [f'Pergunta feita ao cliente: {item.pergunta}', f'Resposta do cliente: {resposta_str}']
    if item.instrucoes_ia:
        partes.append(f'Instrucoes especificas pra validar esta pergunta: {item.instrucoes_ia}')
    if contexto_coletado:
        partes.append(f'Dados ja coletados nesta conversa: {json.dumps(contexto_coletado, ensure_ascii=False)}')

    return [
        {'role': 'system', 'content': persona},
        {'role': 'user', 'content': '\n'.join(partes)},
    ]


def validar_com_ia(item, resposta, tenant, contexto_coletado=None):
    """Valida `resposta` pra `item` via LLM. Devolve dict normalizado com 7
    chaves (ver `_resultado`). NUNCA levanta: qualquer falha (sem integracao
    de IA no tenant, timeout, erro HTTP, JSON invalido) cai em fallback com
    `valida=None` — mesmo contrato "aceita com ressalva" ja usado pela
    cascata deterministica em `services/validacao.py`."""
    from apps.automacao.services.ia import chamar_llm, integracao_ia_do_tenant

    resposta_str = '' if resposta is None else str(resposta).strip()

    integracao = integracao_ia_do_tenant(tenant)
    if not integracao:
        return _resultado(None, resposta_str, 'fallback', _MOTIVO_IA_INDISPONIVEL)

    mensagens = _montar_mensagens(item, resposta_str, tenant, contexto_coletado)
    try:
        # chamar_llm ja blinda erro de rede/HTTP internamente e devolve None;
        # o try aqui e defesa extra caso algo escape disso (ex: exception
        # antes do try interno dela, ou um mock de teste que levanta direto).
        texto = chamar_llm(integracao, mensagens, timeout=_TIMEOUT_IA, max_tokens=_MAX_TOKENS)
    except Exception:
        logger.exception('Falha inesperada chamando LLM pra validar item %s', getattr(item, 'pk', None))
        return _resultado(None, resposta_str, 'fallback', _MOTIVO_IA_INDISPONIVEL)

    if not texto:
        return _resultado(None, resposta_str, 'fallback', _MOTIVO_IA_INDISPONIVEL)

    try:
        dados = json.loads(_extrair_json(texto))
    except (ValueError, TypeError):
        return _resultado(None, resposta_str, 'fallback', _MOTIVO_IA_RESPOSTA_INVALIDA)

    if not isinstance(dados, dict):
        return _resultado(None, resposta_str, 'fallback', _MOTIVO_IA_RESPOSTA_INVALIDA)

    valido = bool(dados.get('valido'))
    try:
        confianca = float(dados.get('confianca'))
    except (TypeError, ValueError):
        confianca = 0.0
    confianca = max(0.0, min(1.0, confianca))

    intencao = str(dados.get('intencao_detectada') or _INTENCAO_PADRAO).strip().lower()
    if intencao not in _INTENCOES_VALIDAS:
        intencao = _INTENCAO_PADRAO

    mensagem_bot = str(dados.get('mensagem_bot') or '').strip()
    motivo_invalido = str(dados.get('motivo_invalido') or '').strip()
    dados_extraidos = dados.get('dados_extraidos')

    # Confianca abaixo do minimo: mesmo com valido=true, nao confia o
    # suficiente pra liberar o dado no CRM sem revisao. Trata como invalida
    # (limiar documentado em _CONFIANCA_MINIMA).
    if valido and confianca < _CONFIANCA_MINIMA:
        valido = False
        motivo_invalido = motivo_invalido or _MOTIVO_IA_CONFIANCA_BAIXA

    if valido:
        valor = dados_extraidos if dados_extraidos else resposta_str
        return _resultado(True, valor, 'ia', '', confianca, intencao, mensagem_bot)

    # "erro" carrega a mensagem humanizada (o que o bot vai reperguntar pro
    # cliente); motivo_invalido fica so pra log/telemetria interna.
    erro = mensagem_bot or motivo_invalido or _MOTIVO_IA_REPROVADO
    return _resultado(False, None, 'ia', erro, confianca, intencao, mensagem_bot)
