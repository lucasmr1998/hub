"""
Categorizacao da mensagem de erro do HubSoft em rotulos estaveis pro painel.

Resiliencia a mudanca de wording: tabela de patterns regex case-insensitive.
Pra cobrir uma nova frase de erro, basta adicionar regex aqui (nada de mudar
chamadores). Default 'outro' garante que toda tentativa de falha cai em
alguma categoria visivel.
"""
import re


CATEGORIA_OUTRO = 'outro'

_PATTERNS = [
    ('tecnico_ocupado', [
        r'técnic[oa].*ocupad',
        r'sem disponibilidade.*técnic',
        r'agenda do técnic',
        r'técnic[oa].*indispon[íi]vel',
        r'tecnico.*ocupad',
        r'tecnico.*indispon[íi]vel',
    ]),
    ('slot_indisponivel', [
        r'hor[áa]rio.*indispon[íi]vel',
        r'hor[áa]rio.*ocupad',
        r'slot.*ocupad',
        r'sem hor[áa]rio',
        r'agenda.*cheia',
        r'agenda.*lotad',
        r'agenda.*indispon[íi]vel',
    ]),
    ('data_invalida', [
        r'data.*inv[áa]lid',
        r'data.*passad',
        r'data anterior',
        r'data.*fora do prazo',
        r'data.*nao.*permitid',
    ]),
    ('id_invalido', [
        r'id_atendimento.*n[ãa]o',
        r'atendimento.*inexist',
        r'atendimento.*n[ãa]o encontrad',
        r'id.*inv[áa]lid',
        r'parametros.*obrigat',
    ]),
]


def categorizar_falha_hubsoft(mensagem: str) -> str:
    """Retorna uma das CATEGORIAS_FALHA do model OrdemServicoTentativa.

    Default: 'outro'. Funciona pra string vazia/None (retorna 'outro').
    """
    if not mensagem:
        return CATEGORIA_OUTRO
    texto = str(mensagem).lower()
    for categoria, patterns in _PATTERNS:
        for pat in patterns:
            if re.search(pat, texto, flags=re.IGNORECASE):
                return categoria
    return CATEGORIA_OUTRO


# Patterns especificos de erros de contrato (criar/aceitar/anexar)
_PATTERNS_CONTRATO = [
    ('contrato_ja_existe', [
        r'j[áa] existe contrato',
        r'contrato.*duplicad',
        r'contrato.*ja.*ativ',
    ]),
    ('cliente_sem_servico', [
        r'cliente.*sem servi[cç]',
        r'id_cliente_servico.*n[ãa]o',
        r'servi[çc]o.*n[ãa]o encontrad',
    ]),
    ('modelo_nao_encontrado', [
        r'modelo.*n[ãa]o encontrad',
        r'id_contrato.*inv[áa]lid',
        r'modelo de contrato',
    ]),
    ('documento_rejeitado', [
        r'arquivo.*rejeitad',
        r'mime.*inv[áa]lid',
        r'documento.*formato',
        r'anexo.*inv[áa]lid',
        r'tipo de arquivo',
    ]),
    ('dados_invalidos', [
        r'cpf.*inv[áa]lid',
        r'campo.*obrigat[óo]ri',
        r'nome.*vazio',
        r'autoriza[cç][ãa]o.*n[ãa]o.*pode',
    ]),
    ('token_expirado', [
        r'token.*expir',
        r'autoriza[cç][ãa]o.*inv[áa]lid',
        r'unauthor',
        r'401',
    ]),
    ('cliente_inexistente', [
        r'cliente.*n[ãa]o encontrad',
        r'cliente.*inexist',
        r'cpf.*n[ãa]o.*localiz',
    ]),
]


def categorizar_falha_contrato(mensagem: str) -> str:
    """Retorna uma das CATEGORIAS_FALHA_CONTRATO do model ContratoTentativa.

    Cobre erros de criar/anexar/aceitar contrato no HubSoft.
    Default: 'outro'.
    """
    if not mensagem:
        return CATEGORIA_OUTRO
    texto = str(mensagem).lower()
    for categoria, patterns in _PATTERNS_CONTRATO:
        for pat in patterns:
            if re.search(pat, texto, flags=re.IGNORECASE):
                return categoria
    return CATEGORIA_OUTRO
