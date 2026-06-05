from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dicionario, chave):
    """Acessa item de dict por chave dinamica no template.

    Uso: {{ meu_dict|get_item:variavel_chave }}
    Retorna '' se nao achar (evita TemplateSyntaxError).
    """
    if not isinstance(dicionario, dict):
        return ''
    return dicionario.get(chave, '')
