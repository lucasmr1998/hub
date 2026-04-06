from django import template

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
