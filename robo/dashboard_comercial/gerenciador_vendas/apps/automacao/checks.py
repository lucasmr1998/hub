"""
Self-check de boot da engine de automação.

Pega o "gremlin": se a rota da automação sumir do `urls.py` do projeto (o app
carrega mas o editor dá 404), o `manage.py check` avisa em vez de a gente
descobrir via 404 silencioso.

(O caso de `apps.automacao` sumir do INSTALLED_APPS não dá pra auto-detectar
daqui — o app nem carrega; mas esse caso quebra tudo de forma barulhenta.)
"""
from django.core.checks import Warning, register


@register()
def automacao_wiring_check(app_configs, **kwargs):
    from django.urls import reverse, NoReverseMatch
    try:
        reverse('automacao:editor')
    except NoReverseMatch:
        return [Warning(
            'Engine de automação NÃO está ligada nas URLs do projeto.',
            hint="Adicione  path('automacao/', include('apps.automacao.urls'))  "
                 "em gerenciador_vendas/urls.py (a linha some às vezes por edição externa).",
            id='automacao.W001',
        )]
    except Exception:
        pass
    return []
