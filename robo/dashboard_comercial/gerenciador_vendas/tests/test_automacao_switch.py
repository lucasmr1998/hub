"""
Testes do nó `switch` (roteador de N saídas / saídas dinâmicas).

Puro unit, sem DB. Cobre:
- saídas derivadas dos casos (config) + `default` no fim
- roteamento pro caso que casa (normalizado: trim + minúsculas)
- fallback pra `default` quando nada casa
- resolução de `{{...}}` no valor testado
- validar_config (sem valor / sem casos)
- backward-compat: nó estático devolve `self.saidas`
"""
from types import SimpleNamespace

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kwargs):
    tenant = SimpleNamespace(pk=1, slug='alpha')
    return Contexto(tenant=tenant, **kwargs)


def test_no_registrado():
    assert tipo_por_slug('switch') is not None


def test_saidas_dinamicas_dos_casos():
    no = tipo_por_slug('switch')
    saidas = no.saidas_de({'casos': 'bug\nduvida\nfinanceiro'})
    assert saidas == ['bug', 'duvida', 'financeiro', 'default']


def test_saidas_ignora_linhas_vazias_e_duplicadas():
    no = tipo_por_slug('switch')
    saidas = no.saidas_de({'casos': 'bug\n\n  bug \nduvida\ndefault'})
    assert saidas == ['bug', 'duvida', 'default']


def test_roteia_pro_caso_que_casa():
    no = tipo_por_slug('switch')
    ctx = _ctx(variaveis={'cat': 'bug'})
    res = no.executar({'valor': '{{var.cat}}', 'casos': 'bug\nduvida'}, {}, ctx)
    assert res.status == 'ok'
    assert res.branch == 'bug'
    assert res.output['caso'] == 'bug'


def test_casa_normalizado():
    no = tipo_por_slug('switch')
    ctx = _ctx(variaveis={'cat': '  Bug '})
    res = no.executar({'valor': '{{var.cat}}', 'casos': 'bug\nduvida'}, {}, ctx)
    assert res.branch == 'bug'


def test_fallback_default():
    no = tipo_por_slug('switch')
    ctx = _ctx(variaveis={'cat': 'qualquer outra coisa'})
    res = no.executar({'valor': '{{var.cat}}', 'casos': 'bug\nduvida'}, {}, ctx)
    assert res.branch == 'default'
    assert res.output['caso'] is None


def test_validar_config_sem_valor():
    no = tipo_por_slug('switch')
    assert no.validar_config({'casos': 'bug'}) != []


def test_validar_config_sem_casos():
    no = tipo_por_slug('switch')
    assert no.validar_config({'valor': '{{var.x}}'}) != []


def test_no_estatico_mantem_saidas_fixas():
    # backward-compat: nó comum não tem saídas dinâmicas
    no = tipo_por_slug('set_fields')
    assert no.saidas_de({'qualquer': 'coisa'}) == no.saidas
