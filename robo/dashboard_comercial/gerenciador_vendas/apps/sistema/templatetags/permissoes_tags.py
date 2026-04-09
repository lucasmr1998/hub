import re
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()


@register.simple_tag(takes_context=True)
def tem_funcionalidade(context, codigo):
    """
    Verifica se o usuário tem a funcionalidade.
    Retorna True se superuser, sem perfil (legado), ou funcionalidade presente.

    Uso no template:
        {% load permissoes_tags %}
        {% tem_funcionalidade 'comercial.ver_pipeline' as pode_pipeline %}
        {% if pode_pipeline %}...{% endif %}
    """
    try:
        if context.get('is_superuser'):
            return True
        user_funcs = context.get('user_funcs')
        if user_funcs is None:
            return True
        return codigo in user_funcs
    except Exception:
        return True


@register.filter(name='whatsapp_format')
def whatsapp_format(value):
    """Formata texto com marcacoes do WhatsApp: *negrito*, _italico_, ~tachado~, quebras de linha."""
    if not value:
        return ''
    text = escape(str(value))
    text = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\b_([^_]+)_\b', r'<em>\1</em>', text)
    text = re.sub(r'~([^~]+)~', r'<del>\1</del>', text)
    text = re.sub(r'```([^`]+)```', r'<code>\1</code>', text)
    text = text.replace('\n', '<br>')
    return mark_safe(text)
