"""Template tags da landing page (renderizar bloco aninhado, campo, etc.)."""
from django import template
from django.template.loader import get_template
from django.utils.safestring import mark_safe

from apps.marketing.landing_pages.catalog import get_campo
from apps.marketing.landing_pages.renderer import renderizar_bloco

register = template.Library()


@register.filter(name='render_bloco')
def render_bloco(bloco_dict):
    """Renderiza um sub-bloco (usado por blocos container tipo `colunas`)."""
    if not isinstance(bloco_dict, dict):
        return ''
    return mark_safe(renderizar_bloco(bloco_dict))


@register.filter(name='render_campo')
def render_campo(campo_dict):
    """Renderiza um campo do formulario a partir do dict {tipo, name, props}."""
    if not isinstance(campo_dict, dict):
        return ''
    tipo = campo_dict.get('tipo', '')
    spec = get_campo(tipo)
    if not spec:
        return mark_safe(f'<div style="color:#dc2626;font-family:monospace;font-size:12px;">[campo desconhecido: {tipo}]</div>')
    # Props: defaults do campo + props customizadas + name explicito do campo
    props = dict(spec.defaults)
    props.update(campo_dict.get('props', {}))
    if 'name' in campo_dict:
        props['name'] = campo_dict['name']
    try:
        tpl = get_template(spec.template)
        return mark_safe(tpl.render({'props': props, 'campo_tipo': tipo}))
    except Exception as exc:
        return mark_safe(f'<div style="color:#dc2626;font-family:monospace;font-size:12px;">[erro campo {tipo}: {exc}]</div>')


@register.filter(name='get_formulario')
def get_formulario(form_id):
    """Resolve FormularioLanding pelo id pra renderizar dentro do bloco `form`."""
    if not form_id:
        return None
    from apps.marketing.landing_pages.models import FormularioLanding
    try:
        return FormularioLanding.all_tenants.filter(pk=int(form_id)).first()
    except (ValueError, TypeError):
        return None
