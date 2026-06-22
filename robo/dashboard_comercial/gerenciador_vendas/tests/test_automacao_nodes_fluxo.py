"""Testes dos nós de fluxo `if` e `delay` (P2). Puro unit, sem DB."""
from types import SimpleNamespace

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


# -- if --------------------------------------------------------------------

def test_if_registrado():
    assert tipo_por_slug('if') is not None


def test_if_igual_true():
    no = tipo_por_slug('if')
    ctx = _ctx(variaveis={'x': 'sim'})
    res = no.executar({'esquerda': '{{var.x}}', 'operador': 'igual', 'direita': 'sim'}, {}, ctx)
    assert res.branch == 'true'
    assert res.output['resultado'] is True


def test_if_maior_numerico():
    no = tipo_por_slug('if')
    ctx = _ctx(variaveis={'score': '8'})
    res = no.executar({'esquerda': '{{var.score}}', 'operador': 'maior', 'direita': '7'}, {}, ctx)
    assert res.branch == 'true'


def test_if_false():
    no = tipo_por_slug('if')
    res = no.executar({'esquerda': 'a', 'operador': 'igual', 'direita': 'b'}, {}, _ctx())
    assert res.branch == 'false'


def test_if_vazio():
    no = tipo_por_slug('if')
    res = no.executar({'esquerda': '', 'operador': 'vazio'}, {}, _ctx())
    assert res.branch == 'true'


def test_if_operador_invalido():
    assert tipo_por_slug('if').validar_config({'operador': 'xpto'}) != []


# -- delay -----------------------------------------------------------------

def test_delay_registrado():
    assert tipo_por_slug('delay') is not None


def test_delay_pausa():
    no = tipo_por_slug('delay')
    res = no.executar({'valor': 5, 'unidade': 'minutos'}, {}, _ctx())
    assert res.status == 'aguardando'
    assert res.output['aguardar_segundos'] == 300


def test_delay_unidade_invalida():
    assert tipo_por_slug('delay').validar_config({'valor': 1, 'unidade': 'anos'}) != []
