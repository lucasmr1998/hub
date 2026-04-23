"""
Filtros de template para serializar dados como JSON seguro em HTML.

Uso:
    {% load json_filters %}
    <div data-extras='{{ obj.config|jsonify }}'>
"""
import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='jsonify')
def jsonify(value):
    """
    Serializa um dict/list/None como JSON valido pra uso em atributos HTML.

    Resolve o problema de Django renderizar dicts Python com aspas simples,
    que quebram HTML data-* quando o atributo usa aspas simples.

    - None -> "{}"
    - dict/list -> json.dumps com aspas duplas
    - escapa apostrofes pra &#39; (seguro dentro de data-x='...')
    """
    if value is None or value == '':
        return mark_safe('{}')
    if isinstance(value, str):
        # Ja e string (pode ser JSON ou texto comum) — valida ou retorna vazio
        try:
            json.loads(value)
            return mark_safe(value.replace("'", "&#39;"))
        except (ValueError, TypeError):
            return mark_safe('{}')
    try:
        s = json.dumps(value, ensure_ascii=False)
        # Escapa apostrofe pra nao quebrar data-x='...'
        return mark_safe(s.replace("'", "&#39;"))
    except (TypeError, ValueError):
        return mark_safe('{}')
