"""
Modelos (templates) de slide.

Cada modelo e uma lista de blocos ja posicionados na grade 12x9 do slide. Ao
criar um slide a partir de um modelo, os blocos ja nascem no lugar; os slots de
grafico nascem como bloco tipo='widget' SEM widget (o usuario clica e escolhe
qual widget do dashboard entra ali).

Nada de layout hardcoded na view: a estrutura vive aqui e a API so instancia.
"""

# Slot de grafico/KPI vazio: o editor mostra "Escolher widget" e abre o picker.
def _slot(x, y, w, h):
    return {'tipo': 'widget', 'conteudo': {}, 'layout': {'x': x, 'y': y, 'w': w, 'h': h}}


def _titulo(texto='Titulo da secao', subtitulo='', x=0, y=0, w=12, h=1):
    return {'tipo': 'titulo_secao',
            'conteudo': {'texto': texto, 'subtitulo': subtitulo},
            'layout': {'x': x, 'y': y, 'w': w, 'h': h}}


def _texto(texto='Clique pra editar o comentario', x=0, y=0, w=4, h=7):
    return {'tipo': 'texto',
            'conteudo': {'texto': texto, 'align': 'left', 'tamanho': 16},
            'layout': {'x': x, 'y': y, 'w': w, 'h': h}}


MODELOS = {
    'branco': {
        'label': 'Em branco',
        'icone': 'bi-square',
        'descricao': 'Slide vazio pra montar do zero.',
        'blocos': [],
    },
    'capa': {
        'label': 'Capa',
        'icone': 'bi-file-earmark-text',
        'descricao': 'Titulo grande + subtitulo. Bom pro primeiro slide.',
        'blocos': [
            _titulo('Titulo da apresentacao', 'Subtitulo / periodo', x=0, y=3, w=12, h=3),
        ],
    },
    'secao': {
        'label': 'Divisor de secao',
        'icone': 'bi-hr',
        'descricao': 'So o titulo da secao, pra separar blocos da apresentacao.',
        'blocos': [
            _titulo('Nome da secao', '', x=0, y=4, w=12, h=2),
        ],
    },
    'kpis': {
        'label': 'Linha de KPIs + grafico',
        'icone': 'bi-123',
        'descricao': '4 indicadores no topo e um grafico grande embaixo.',
        'blocos': [
            _titulo('Indicadores', '', x=0, y=0, w=12, h=1),
            _slot(0, 1, 3, 2), _slot(3, 1, 3, 2), _slot(6, 1, 3, 2), _slot(9, 1, 3, 2),
            _slot(0, 3, 12, 6),
        ],
    },
    'duas_colunas': {
        'label': 'Dois graficos',
        'icone': 'bi-layout-split',
        'descricao': 'Dois graficos lado a lado, pra comparar.',
        'blocos': [
            _titulo('Comparativo', '', x=0, y=0, w=12, h=1),
            _slot(0, 1, 6, 8), _slot(6, 1, 6, 8),
        ],
    },
    'grafico_comentario': {
        'label': 'Grafico + comentario',
        'icone': 'bi-chat-left-text',
        'descricao': 'Um grafico grande e um espaco pro seu comentario ao lado.',
        'blocos': [
            _titulo('Analise', '', x=0, y=0, w=12, h=1),
            _slot(0, 1, 8, 8),
            _texto('Escreva aqui a leitura do numero: o que explica, o que fazer.', x=8, y=1, w=4, h=8),
        ],
    },
}


def listar():
    """Modelos pro picker do editor (sem os blocos, que sao detalhe da API)."""
    return [
        {'slug': slug, 'label': m['label'], 'icone': m['icone'], 'descricao': m['descricao']}
        for slug, m in MODELOS.items()
    ]


def blocos_do_modelo(slug):
    """Blocos de um modelo. Slug desconhecido = slide em branco."""
    return (MODELOS.get(slug) or MODELOS['branco'])['blocos']
