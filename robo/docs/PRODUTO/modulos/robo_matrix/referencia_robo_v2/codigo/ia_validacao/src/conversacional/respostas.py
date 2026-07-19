"""Geração das mensagens pro cliente — PRÓPRIA do conversacional.

Cada TIPO de erro tem uma resposta específica que explica o problema e
PEDE A INFORMAÇÃO DE NOVO de forma clara (não um "não entendi" genérico).
A resposta escala conforme as tentativas: 1ª gentil, 2ª com exemplo, e
ao exceder o máximo → transbordo pra atendente.

A mensagem de sucesso/próxima pergunta sai do Django (regra.msg_sucesso /
pergunta_padrao). Aqui só montamos; a humanização (gpt-4o) é aplicada por
cima pelo orquestrador via humanizador.humanizar_pergunta.
"""
from __future__ import annotations

# ── Mensagens específicas por motivo de erro ──────────────────────────
# {pergunta} é substituído pela pergunta da etapa (pra re-solicitar).
_MOTIVO_BASE: dict[str, str] = {
    # CPF
    'cpf_nao_identificado': 'Não consegui identificar um CPF na sua mensagem. '
                            'Pode me mandar os 11 números do CPF do titular?',
    'cpf_invalido':         'Esse CPF não passou na verificação dos dígitos. '
                            'Pode conferir e mandar de novo?',
    # CEP
    'cep_nao_identificado': 'Não achei um CEP aí. Pode me enviar os 8 números do CEP?',
    'cep_nao_existe':       'Esse CEP não foi encontrado nos Correios. '
                            'Pode conferir os números pra mim?',
    # Nome
    'sobrenome_faltando':   'Preciso do seu nome *completo* (nome e sobrenome). '
                            'Pode me mandar?',
    'palavra_muito_curta':  'O nome ficou incompleto. Pode digitar seu nome '
                            'completo, por favor?',
    'tamanho_invalido':     'Não consegui validar esse nome. Pode escrever seu '
                            'nome completo?',
    'nome_invalido':        'Pode me dizer seu nome completo (nome e sobrenome)?',
    # Data
    'menor_de_idade':       'O cadastro precisa ser feito por maior de 18 anos. '
                            'Pode confirmar a data de nascimento do titular?',
    'idade_invalida':       'Essa data não parece válida. Pode mandar no formato '
                            'DD/MM/AAAA?',
    'formato_invalido':     'Não entendi a data. Me manda no formato DD/MM/AAAA '
                            '(ex: 25/12/1990)?',
    'data_invalida':        'Pode me mandar sua data de nascimento no formato '
                            'DD/MM/AAAA?',
    # E-mail / número
    'email_invalido':       'Esse e-mail não parece certo. Pode digitar de novo? '
                            '(ex: nome@email.com)',
    'numero_invalido':      'Qual o número da residência? Se não tiver, é só '
                            'dizer "sem número".',
    # Opção / confirmação
    'opcao_nao_reconhecida': 'Não entendi a opção. Pode responder com o número '
                             'da opção desejada?',
    'confirmacao_ambigua':  'Só pra confirmar: você quer seguir? Responde com '
                            '*sim* ou *não*, por favor.',
    'imagem_ausente':       'Preciso que você envie a foto pra continuar. Pode '
                            'mandar a imagem?',
    'resposta_vazia':       'Não recebi sua resposta. Pode escrever de novo?',
}

# Pré-ajuda extra na 2ª tentativa (exemplo concreto), por extractor_tipo.
_EXEMPLO_POR_TIPO: dict[str, str] = {
    'cpf':             'Exemplo: 123.456.789-09 (só os números também serve).',
    'cep':             'Exemplo: 64000-000.',
    'data_nascimento': 'Exemplo: 05/10/1990.',
    'email':           'Exemplo: maria@gmail.com.',
}


def mensagem_erro(
    regra: dict,
    motivo: str,
    *,
    tentativa: int = 1,
) -> str:
    """Mensagem específica de erro que re-solicita a informação.

    Prioriza a msg_erro configurada na regra (Django); se não houver,
    usa a mensagem específica do motivo. Na 2ª+ tentativa, agrega um
    exemplo concreto pra ajudar.
    """
    base = (regra.get('msg_erro') or '').strip()
    if not base:
        base = _MOTIVO_BASE.get(motivo, '').strip()
    if not base:
        # último recurso: re-pergunta a própria etapa
        base = (regra.get('pergunta_padrao') or
                'Pode me enviar essa informação de novo?').strip()

    if tentativa >= 2:
        exemplo = _EXEMPLO_POR_TIPO.get(regra.get('extractor_tipo', ''), '')
        if exemplo and exemplo not in base:
            base = f'{base}\n{exemplo}'
    return base


def mensagem_max_tentativas(regra: dict) -> str:
    """Mensagem ao exceder o máximo de tentativas (antes do transbordo)."""
    msg = (regra.get('msg_max_tentativas') or '').strip()
    return msg or ('Vou te transferir pra um de nossos atendentes pra te '
                   'ajudar melhor com isso, tá? 😊')


def mensagem_sucesso(regra: dict, *, extracted: str = '') -> str:
    """Mensagem de sucesso configurada na regra (pode citar {extracted})."""
    msg = (regra.get('msg_sucesso') or '').strip()
    if not msg:
        return ''
    if '{extracted}' in msg:
        msg = msg.replace('{extracted}', extracted or '')
    return msg.strip()


def deve_transbordar(regra: dict, tentativa: int) -> bool:
    """True se já estourou o máximo de tentativas e a regra força transbordo."""
    maximo = int(regra.get('max_tentativas') or 3)
    if tentativa < maximo:
        return False
    return bool(regra.get('forcar_transbordo_apos_max', True))
