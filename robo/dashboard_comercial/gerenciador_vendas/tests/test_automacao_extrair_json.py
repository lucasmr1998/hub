"""Nó `extrair_json` — unit (sem DB, sem rede, sem ORM)."""
from types import SimpleNamespace

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrado():
    assert tipo_por_slug('extrair_json') is not None


def test_json_puro():
    no = tipo_por_slug('extrair_json')
    res = no.executar({'origem': '{"nome": "Ana", "idade": 30}'}, {}, _ctx())
    assert res.branch == 'sucesso'
    assert res.output == {'nome': 'Ana', 'idade': 30}


def test_json_com_cerca_de_codigo_markdown():
    no = tipo_por_slug('extrair_json')
    origem = '```json\n{"ok": true}\n```'
    res = no.executar({'origem': origem}, {}, _ctx())
    assert res.branch == 'sucesso'
    assert res.output == {'ok': True}


def test_texto_com_lixo_em_volta_pega_o_objeto():
    no = tipo_por_slug('extrair_json')
    origem = 'Aqui está o resultado: {"campo": "valor"} Obrigado!'
    res = no.executar({'origem': origem}, {}, _ctx())
    assert res.branch == 'sucesso'
    assert res.output == {'campo': 'valor'}


def test_dict_full_match_direto_sem_parsear_string():
    no = tipo_por_slug('extrair_json')
    ctx = _ctx(variaveis={'dados': {'a': 1}})
    res = no.executar({'origem': '{{var.dados}}'}, {}, ctx)
    assert res.branch == 'sucesso'
    assert res.output == {'a': 1}


def test_invalido_vira_erro():
    no = tipo_por_slug('extrair_json')
    res = no.executar({'origem': 'isso não é json nem tem chaves'}, {}, _ctx())
    assert res.branch == 'erro'
    assert res.erro


def test_origem_vazia_vira_erro():
    no = tipo_por_slug('extrair_json')
    res = no.executar({'origem': ''}, {}, _ctx())
    assert res.branch == 'erro'


def test_salvar_em_promove_pra_var():
    no = tipo_por_slug('extrair_json')
    res = no.executar({'origem': '{"a": 1}', 'salvar_em': 'dados'}, {}, _ctx())
    assert res.branch == 'sucesso'
    assert res.promote == {'dados': {'a': 1}}


def test_sem_salvar_em_nao_promove():
    no = tipo_por_slug('extrair_json')
    res = no.executar({'origem': '{"a": 1}'}, {}, _ctx())
    assert res.branch == 'sucesso'
    assert not res.promote


def test_lista_vira_output_valor():
    no = tipo_por_slug('extrair_json')
    res = no.executar({'origem': '[1, 2, 3]'}, {}, _ctx())
    assert res.branch == 'sucesso'
    assert res.output == {'valor': [1, 2, 3]}


def test_validar_config_exige_origem():
    no = tipo_por_slug('extrair_json')
    assert no.validar_config({})
    assert not no.validar_config({'origem': '{{nodes.agente.resposta}}'})
