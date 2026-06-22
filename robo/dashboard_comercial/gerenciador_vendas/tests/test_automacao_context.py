"""
Testes da fundação da engine de automação (D1): Contexto + resolvedor de template.

Puro unit, sem DB — o resolvedor não toca ORM. Usa objetos leves (SimpleNamespace)
no lugar de models reais.

Cobre o contrato híbrido `{{ ... }}`:
- dot-notation em entidade, var e nodes
- full-match preserva o tipo bruto (dict passa inteiro entre nós)
- interpolação em texto misto vira string (dict→JSON)
- não resolvido fica literal
- resolução recorre em dict/list
- tenant obrigatório
- serializar() devolve só ids + JSON
"""
import json
from types import SimpleNamespace

import pytest

from apps.automacao.nodes import Contexto


def _ctx(**kwargs):
    tenant = SimpleNamespace(pk=1, slug='alpha', nome='Alpha')
    return Contexto(tenant=tenant, **kwargs)


def test_resolve_atributo_de_entidade():
    lead = SimpleNamespace(nome='Lucas', telefone='+5581999')
    ctx = _ctx(lead=lead)
    assert ctx.resolver('Oi {{lead.nome}}, tudo bem?') == 'Oi Lucas, tudo bem?'


def test_resolve_tenant_slug():
    assert _ctx().resolver('tenant={{tenant.slug}}') == 'tenant=alpha'


def test_resolve_var():
    ctx = _ctx(variaveis={'token': 'abc123'})
    assert ctx.resolver('Bearer {{var.token}}') == 'Bearer abc123'


def test_resolve_nodes_aninhado():
    ctx = _ctx(nodes={'http_1': {'body': {'access_token': 'xyz'}}})
    assert ctx.resolver('{{nodes.http_1.body.access_token}}') == 'xyz'


def test_full_match_preserva_tipo_bruto():
    ctx = _ctx(nodes={'http_1': {'body': {'x': 1, 'y': [2, 3]}}})
    out = ctx.resolver('{{nodes.http_1.body}}')
    assert out == {'x': 1, 'y': [2, 3]}  # dict inteiro, não string


def test_interpolacao_de_dict_vira_json():
    ctx = _ctx(variaveis={'obj': {'a': 1}})
    assert ctx.resolver('valor={{var.obj}}') == 'valor={"a": 1}'


def test_nao_resolvido_fica_literal():
    ctx = _ctx()
    assert ctx.resolver('{{var.naoexiste}}') == '{{var.naoexiste}}'
    # lead é None → caminho não resolve → literal
    assert ctx.resolver('{{lead.nome}}') == '{{lead.nome}}'


def test_multiplos_tokens_no_mesmo_texto():
    ctx = _ctx(variaveis={'a': 'X', 'b': 'Y'})
    assert ctx.resolver('{{var.a}}-{{var.b}}') == 'X-Y'


def test_resolver_recorre_em_dict_e_list():
    ctx = _ctx(variaveis={'n': 'Lucas'})
    entrada = {'nome': '{{var.n}}', 'tags': ['fixo', '{{var.n}}']}
    assert ctx.resolver(entrada) == {'nome': 'Lucas', 'tags': ['fixo', 'Lucas']}


def test_valor_none_interpola_vazio():
    ctx = _ctx(variaveis={'x': None})
    # 'x' existe mas é None → interpola como '' (não fica literal)
    assert ctx.resolver('inicio[{{var.x}}]fim') == 'inicio[]fim'


def test_tenant_obrigatorio():
    with pytest.raises(ValueError):
        Contexto(tenant=None)


def test_promover_vira_var():
    ctx = _ctx()
    ctx.promover('email', 'a@b.com')
    assert ctx.resolver('{{var.email}}') == 'a@b.com'


def test_serializar_so_ids_e_json():
    lead = SimpleNamespace(pk=7, nome='Lucas')
    ctx = _ctx(lead=lead, variaveis={'x': 1}, nodes={'h': {'ok': True}})
    s = ctx.serializar()
    assert s['tenant_id'] == 1
    assert s['entidades']['lead'] == 7
    assert s['entidades']['oportunidade'] is None
    assert s['variaveis'] == {'x': 1}
    assert s['nodes'] == {'h': {'ok': True}}
    json.dumps(s)  # tem que ser JSON-serializável (sem objetos crus)
