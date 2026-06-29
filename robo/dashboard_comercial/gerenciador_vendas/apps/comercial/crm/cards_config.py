"""Catalogo de campos disponiveis pro card customizavel do kanban.

Cada vendedor escolhe quais ver no seu kanban (max 5). Admin do tenant define
o default em ConfiguracaoCRM.campos_card_padrao.

Pra adicionar campo novo: adicione no CAMPOS_CARD_DISPONIVEIS + implementar
`extrair_valor_campo()` no view do pipeline.
"""

# Cada entrada: (slug, label, categoria, icone bi-*)
CAMPOS_CARD_DISPONIVEIS = [
    # Identidade
    ('nome',              'Nome do lead',        'identidade', 'bi-person'),
    ('telefone',          'Telefone',            'identidade', 'bi-telephone'),
    ('cpf',               'CPF',                 'identidade', 'bi-card-text'),
    ('email',             'Email',               'identidade', 'bi-envelope'),
    # Comercial
    ('valor_estimado',    'Valor estimado',      'comercial',  'bi-currency-dollar'),
    ('plano',             'Plano escolhido',     'comercial',  'bi-wifi'),
    # `responsavel` e `responsavel_avatar` sairam da personalizacao —
    # sempre aparecem compactos no rodape do card (avatar + nome).
    # Evita duplicidade no meio do card.
    # Status
    # `tempo_no_estagio` saiu da personalizacao — sempre aparece compacto
    # no rodape do card (ao lado do avatar do responsavel). Evita duplicidade.
    ('tags',              'Tags',                'status',     'bi-tag'),
    ('score_externo',     'Score externo',       'status',     'bi-graph-up'),
    ('viabilidade',       'Viabilidade',         'status',     'bi-geo-alt'),
    # Atividade
    ('proxima_tarefa',    'Proxima tarefa',      'atividade',  'bi-check2-square'),
    ('ultima_atividade',  'Ultima atividade',    'atividade',  'bi-activity'),
    # Integracao
    ('id_hubsoft',        'ID HubSoft',          'integracao', 'bi-link-45deg'),
    # Origem (atribuicao da venda — Sprint 1+2+4)
    ('canal',             'Canal de chegada',    'origem',     'bi-chat-dots'),
    ('fonte',             'Fonte / Plataforma',  'origem',     'bi-globe'),
    ('campanha',          'Campanha de origem',  'origem',     'bi-megaphone'),
]

# Defaults razoaveis pra um tenant novo (tempo_no_estagio e responsavel
# saem porque ja aparecem no rodape compacto sempre)
DEFAULT_CAMPOS_CARD = ['nome', 'telefone', 'valor_estimado', 'plano', 'tags']

# Limite maximo de campos visiveis (HubSpot usa 4, RD usa 4, Pipedrive 5)
MAX_CAMPOS_VISIVEIS = 5

CATEGORIAS_LABEL = {
    'identidade': 'Identidade',
    'comercial':  'Comercial',
    'pessoas':    'Pessoas',
    'status':     'Status',
    'atividade':  'Atividade',
    'integracao': 'Integracao',
    'origem':     'Origem / Atribuicao',
}


def campos_validos(lista):
    """Filtra uma lista de slugs mantendo so os que existem e respeita o max."""
    if not lista:
        return list(DEFAULT_CAMPOS_CARD)
    validos_set = {c[0] for c in CAMPOS_CARD_DISPONIVEIS}
    filtrados = [s for s in lista if s in validos_set]
    return filtrados[:MAX_CAMPOS_VISIVEIS]


def resolver_campos_do_usuario(user, config_crm):
    """Resolucao em cascata: preferencia do usuario -> config do tenant -> default global.

    Retorna lista de slugs validos.
    """
    try:
        from apps.comercial.crm.models import PreferenciaUsuarioKanban
        pref = PreferenciaUsuarioKanban.objects.filter(user=user).first()
        if pref and pref.campos:
            return campos_validos(pref.campos)
    except Exception:
        pass
    if config_crm and config_crm.campos_card_padrao:
        return campos_validos(config_crm.campos_card_padrao)
    return list(DEFAULT_CAMPOS_CARD)
