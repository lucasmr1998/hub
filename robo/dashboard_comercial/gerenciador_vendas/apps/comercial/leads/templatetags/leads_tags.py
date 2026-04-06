from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Acessa uma chave de dicionario dinamicamente no template.
    Uso: {{ meu_dict|dict_get:campo.slug }}
    """
    if isinstance(d, dict):
        return d.get(key, '')
    return ''
