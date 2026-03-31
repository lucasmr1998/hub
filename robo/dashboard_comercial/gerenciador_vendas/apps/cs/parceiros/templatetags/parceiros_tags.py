import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='safe_cupom_json')
def safe_cupom_json(cupom):
    """Serializa um cupom para JSON seguro para uso em onclick."""
    data = {
        'titulo': cupom.titulo,
        'descricao': cupom.descricao,
        'codigo': cupom.codigo,
        'parceiro_id': cupom.parceiro_id,
        'tipo_desconto': cupom.tipo_desconto,
        'valor_desconto': str(cupom.valor_desconto),
        'modalidade': cupom.modalidade,
        'custo_pontos': cupom.custo_pontos,
        'nivel_minimo_id': cupom.nivel_minimo_id,
        'quantidade_total': cupom.quantidade_total,
        'limite_por_membro': cupom.limite_por_membro,
        'ativo': cupom.ativo,
        'data_inicio': cupom.data_inicio.strftime('%Y-%m-%dT%H:%M') if cupom.data_inicio else '',
        'data_fim': cupom.data_fim.strftime('%Y-%m-%dT%H:%M') if cupom.data_fim else '',
        'cidades_ids': list(cupom.cidades_permitidas.values_list('id', flat=True)),
    }
    return mark_safe(json.dumps(data).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))
