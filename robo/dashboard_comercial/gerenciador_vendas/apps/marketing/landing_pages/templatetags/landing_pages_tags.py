"""Template tags da landing page (renderizar bloco aninhado, etc.)."""
from django import template
from django.utils.safestring import mark_safe

from apps.marketing.landing_pages.renderer import renderizar_bloco

register = template.Library()


@register.filter(name='render_bloco')
def render_bloco(bloco_dict):
    """Renderiza um sub-bloco (usado por blocos container tipo `colunas`)."""
    if not isinstance(bloco_dict, dict):
        return ''
    return mark_safe(renderizar_bloco(bloco_dict))
