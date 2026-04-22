"""
Fonte única de tipos de condição e operadores usados no motor de
Automações do Pipeline.

Models, views e engine importam daqui pra evitar divergência entre camadas.
"""

# (slug, label)
TIPOS_CONDICAO = [
    ('tag', 'Tag'),
    ('historico_status', 'Status do histórico de contato'),
    ('lead_status_api', 'Status API do lead'),
    ('lead_campo', 'Campo do lead'),
    ('servico_status', 'Status do serviço HubSoft'),
    ('converteu_venda', 'Converteu em venda'),
    ('imagem_status', 'Status de imagem/documento'),
]

OPERADORES = [
    ('igual', 'igual a'),
    ('diferente', 'diferente de'),
    ('existe', 'existe / verdadeiro'),
    ('nao_existe', 'não existe / falso'),
    ('todas_iguais', 'todas iguais a'),
    ('nenhuma_com', 'nenhuma com'),
]


# Dicts prontos pra lookup — evitam scan linear em hotpaths
TIPOS_CONDICAO_DICT = dict(TIPOS_CONDICAO)
OPERADORES_DICT = dict(OPERADORES)
