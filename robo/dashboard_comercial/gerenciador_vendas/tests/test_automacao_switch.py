"""
Testes do nó `switch` (roteador N saídas, modelo "Rules" do n8n).

Puro unit, sem DB. Cada regra é `esquerda [operador] direita → saida`; avalia em
ordem, primeira que casa ganha; nada casou → `default`. Cobre:
- saídas derivadas dos nomes das regras + `default`
- roteamento pela 1ª regra que casa (ordem importa)
- operadores variados (igual, contem) reusando o `_comparar` do if
- resolução de `{{...}}`
- fallback `default`
- validar_config (sem regra / regra sem nome de saída)
- backward-compat: nó estático devolve `self.saidas`
"""
from types import SimpleNamespace

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kwargs):
    tenant = SimpleNamespace(pk=1, slug='alpha')
    return Contexto(tenant=tenant, **kwargs)


_REGRAS = [
    {'esquerda': '{{var.cat}}', 'operador': 'igual', 'direita': 'bug', 'saida': 'bug'},
    {'esquerda': '{{var.cat}}', 'operador': 'igual', 'direita': 'duvida', 'saida': 'duvida'},
    {'esquerda': '{{var.cat}}', 'operador': 'contem', 'direita': 'cobr', 'saida': 'financeiro'},
]


def test_no_registrado():
    assert tipo_por_slug('switch') is not None


def test_saidas_vem_dos_nomes_das_regras():
    no = tipo_por_slug('switch')
    assert no.saidas_de({'regras': _REGRAS}) == ['bug', 'duvida', 'financeiro', 'default']


def test_roteia_pela_regra_que_casa():
    no = tipo_por_slug('switch')
    res = no.executar({'regras': _REGRAS}, {}, _ctx(variaveis={'cat': 'duvida'}))
    assert res.branch == 'duvida'
    assert res.output['saida'] == 'duvida'


def test_operador_contem():
    no = tipo_por_slug('switch')
    res = no.executar({'regras': _REGRAS}, {}, _ctx(variaveis={'cat': 'tenho uma cobranca errada'}))
    assert res.branch == 'financeiro'


def test_primeira_que_casa_ganha():
    no = tipo_por_slug('switch')
    regras = [
        {'esquerda': '{{var.x}}', 'operador': 'contem', 'direita': 'a', 'saida': 'primeira'},
        {'esquerda': '{{var.x}}', 'operador': 'contem', 'direita': 'b', 'saida': 'segunda'},
    ]
    res = no.executar({'regras': regras}, {}, _ctx(variaveis={'x': 'ab'}))
    assert res.branch == 'primeira'  # ordem importa


def test_fallback_default():
    no = tipo_por_slug('switch')
    res = no.executar({'regras': _REGRAS}, {}, _ctx(variaveis={'cat': 'qualquer outra'}))
    assert res.branch == 'default'
    assert res.output['saida'] is None


def test_validar_config_sem_regras():
    no = tipo_por_slug('switch')
    assert no.validar_config({}) != []


def test_validar_config_regra_sem_saida():
    no = tipo_por_slug('switch')
    assert no.validar_config({'regras': [{'esquerda': '{{var.x}}', 'operador': 'igual', 'direita': 'a'}]}) != []


def test_no_estatico_mantem_saidas_fixas():
    no = tipo_por_slug('set_fields')
    assert no.saidas_de({'qualquer': 'coisa'}) == no.saidas
