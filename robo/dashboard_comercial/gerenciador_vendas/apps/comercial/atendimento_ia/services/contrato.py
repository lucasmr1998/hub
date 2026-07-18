"""
Serializacao dos 3 payloads de resposta do contrato com o Matrix.

Contrato IMUTAVEL (extraido do JSON do flow): chaves e TIPOS exatos. Um
mismatch de tipo (bool onde o bot espera string "true"/"false", por
exemplo) nao gera erro nenhum, so faz o bot cair na branch errada em
silencio. Isolado aqui, longe da logica de orquestracao, pra ficar facil de
testar campo a campo (ver tests/test_atendimento_ia_contrato.py).
"""


def _bool_str(valor):
    """O bot le `deve_transbordar`/`needsReception` como STRING "true"/"false",
    nao boolean JSON. Ver tabela de tipos na tarefa da Fase 2."""
    return 'true' if valor else 'false'


def _int(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def ura(item):
    """Bloco `ura` do /ia/proximo-passo. So preenchido quando o item e de
    multipla escolha com 2 a 5 opcoes (o unico formato que o flow do Matrix
    sabe renderizar); fora disso volta o shape vazio, nunca None (o bot
    sempre le `ura.opcoes`, `ura.total_opcoes` etc)."""
    opcoes = list(item.opcoes or []) if item is not None else []
    if item is not None and item.tipo_resposta == 'opcoes' and 2 <= len(opcoes) <= 5:
        return {
            'total_opcoes': len(opcoes),
            'titulo': item.ura_titulo or '',
            'opcoes': [{'texto': o.get('texto', '')} for o in opcoes],
            'pergunta': item.pergunta,
        }
    return {'total_opcoes': 0, 'titulo': '', 'opcoes': [], 'pergunta': ''}


def payload_proximo_passo(
    *, lead_id, status_lead, proximo_passo, proxima_pergunta_id,
    deve_perguntar, deve_transbordar, motivo, intent_detectado,
    mensagem_inicial, item=None,
):
    return {
        'lead_id': _int(lead_id),
        'status_lead': status_lead,  # polimorfico: int 0, "cliente_ativo" ou "em_andamento"
        'proximo_passo': proximo_passo,
        'proxima_pergunta_id': _int(proxima_pergunta_id),
        'deve_perguntar': bool(deve_perguntar),
        'deve_transbordar': _bool_str(deve_transbordar),
        'motivo': motivo or '',
        'intent_detectado': intent_detectado or '',
        'mensagem_inicial': mensagem_inicial or '',
        'ura': ura(item),
    }


def payload_validar(
    *, resposta_correta, resposta_sem_erro_api, retorno_erro_api,
    needs_reception, is_a_client, cancelado, message,
):
    return {
        'resposta_correta': bool(resposta_correta),
        'resposta_sem_erro_api': bool(resposta_sem_erro_api),
        'retorno_erro_api': retorno_erro_api or '',
        'needsReception': _bool_str(needs_reception),
        'isAClient': bool(is_a_client),
        'cancelado': bool(cancelado),
        'message': message or '',
    }


def payload_recontato(
    *, pergunta_id, acao, tentativa, reperguntar, mensagem, deve_transbordar,
):
    return {
        'pergunta_id': _int(pergunta_id),
        'acao': acao,
        'tentativa': _int(tentativa),
        'reperguntar': bool(reperguntar),
        'mensagem': mensagem or '',
        'deve_transbordar': _bool_str(deve_transbordar),
    }
