"""
Fonte única de tipos de condição e operadores usados no motor de
Automações do Pipeline.

Os TIPOS_CONDICAO sao agora derivados do registry em `automacao_condicoes.py`.
Qualquer classe de condicao registrada via `@registrar` aparece aqui
automaticamente — views e models nao precisam conhecer a lista.

Operadores sao definidos aqui porque sao transversais a varios tipos.
"""

OPERADORES = [
    ('igual', 'igual a'),
    ('diferente', 'diferente de'),
    ('existe', 'existe / verdadeiro'),
    ('nao_existe', 'não existe / falso'),
    ('todas_iguais', 'todas iguais a'),
    ('nenhuma_com', 'nenhuma com'),
]

OPERADORES_DICT = dict(OPERADORES)


def _lazy_tipos_condicao():
    """
    Lista de (slug, label) dos tipos registrados.
    Avaliada sob demanda pra evitar problema de import order com apps Django.
    """
    from apps.comercial.crm.services.automacao_condicoes import todos_tipos
    return todos_tipos()


class _TiposLazy:
    """Proxy que delega pras funcoes do registry a cada acesso."""
    def __iter__(self):
        return iter(_lazy_tipos_condicao())

    def __len__(self):
        return len(_lazy_tipos_condicao())

    def __getitem__(self, idx):
        return _lazy_tipos_condicao()[idx]

    def get(self, slug, default=None):
        from apps.comercial.crm.services.automacao_condicoes import tipo_por_slug
        t = tipo_por_slug(slug)
        return t.label if t else default


TIPOS_CONDICAO = _TiposLazy()
TIPOS_CONDICAO_DICT = _TiposLazy()
