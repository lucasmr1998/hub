import re

from django import template
from django.utils import timezone

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


@register.filter(name='rotulo_chave')
def rotulo_chave(valor):
    """Transforma a chave crua de um campo personalizado em rotulo legivel.

    `data_instalacao` vira `Data Instalacao`. O `cut:"_"` que era usado antes
    APAGAVA o underscore e colava as palavras (`dataInstalacao` virava
    `Datainstalacao`), o que quebrava a leitura de toda chave composta.
    """
    return str(valor or '').replace('_', ' ').strip().title()


_ISO_DATA = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}')


@register.filter(name='valor_amigavel')
def valor_amigavel(valor):
    """Formata o valor de um campo personalizado pra exibicao.

    Timestamp ISO (o formato que a engine de automacao grava nos marcadores)
    vira `13/07/2026 15:36`; o resto passa direto. Sem isso, a string ISO crua
    estoura o chip estreito e quebra caractere a caractere na tela.
    """
    texto = str(valor if valor is not None else '')
    if not _ISO_DATA.match(texto):
        return texto
    try:
        from django.utils.dateparse import parse_datetime
        dt = parse_datetime(texto.replace(' ', 'T', 1))
        if dt is None:
            return texto
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        return dt.strftime('%d/%m/%Y %H:%M')
    except (ValueError, TypeError):
        return texto
