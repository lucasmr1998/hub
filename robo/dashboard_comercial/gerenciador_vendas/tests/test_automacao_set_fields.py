"""
Testes do nó de referência `set_fields` (D2).

Puro unit, sem DB. Cobre:
- escrita de variável a partir de template resolvido
- atalho `campo`/`valor` e forma `campos: [...]`
- promoção (promote) que o runtime funde em variaveis
- validar_config (sem campos / campo sem nome)
"""
from types import SimpleNamespace

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kwargs):
    tenant = SimpleNamespace(pk=1, slug='alpha')
    return Contexto(tenant=tenant, **kwargs)


def test_no_registrado():
    assert tipo_por_slug('set_fields') is not None


def test_campo_unico_resolve_template():
    no = tipo_por_slug('set_fields')
    ctx = _ctx(variaveis={'x': 'Lucas'})
    res = no.executar({'campo': 'nome', 'valor': '{{var.x}}'}, {}, ctx)
    assert res.status == 'ok'
    assert res.branch == 'sucesso'
    assert res.output == {'nome': 'Lucas'}
    assert res.promote == {'nome': 'Lucas'}


def test_promocao_funde_em_variaveis():
    no = tipo_por_slug('set_fields')
    ctx = _ctx(variaveis={'x': 'Lucas'})
    res = no.executar({'campo': 'nome', 'valor': '{{var.x}}'}, {}, ctx)
    ctx.aplicar_resultado('set_1', res)
    # a var promovida vira endereçável como {{var.nome}}
    assert ctx.resolver('{{var.nome}}') == 'Lucas'


def test_multiplos_campos():
    no = tipo_por_slug('set_fields')
    ctx = _ctx(variaveis={'n': 'Ana', 'c': 'Recife'})
    config = {'campos': [
        {'nome': 'nome', 'valor': '{{var.n}}'},
        {'nome': 'cidade', 'valor': '{{var.c}}'},
    ]}
    res = no.executar(config, {}, ctx)
    assert res.output == {'nome': 'Ana', 'cidade': 'Recife'}


def test_validar_config_sem_campos():
    no = tipo_por_slug('set_fields')
    assert no.validar_config({}) != []


def test_validar_config_campo_sem_nome():
    no = tipo_por_slug('set_fields')
    erros = no.validar_config({'campos': [{'valor': 'x'}]})
    assert erros != []
