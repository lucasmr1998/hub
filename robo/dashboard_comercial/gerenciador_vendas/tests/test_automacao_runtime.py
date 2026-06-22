"""
Testes do runtime (R1) — o andador do grafo.

Puro unit, sem DB. Cobre: fluxo linear passando dados entre nós, referência a
output de nó anterior via `{{nodes.handle.campo}}`, ramificação por branch de
erro, pausa/retoma, loop guard, validação estrutural.
"""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug
from apps.automacao.nodes.base import BaseNode, NodeResult, registrar
from apps.automacao.runtime import executar_fluxo, validar_fluxo, FluxoInvalido
from tests.test_automacao_http import _FakeResp


@registrar
class _WaitNode(BaseNode):
    """Nó de teste que pausa (simula um futuro delay/wait)."""
    tipo = "_test_wait"
    label = "Test Wait"

    def executar(self, config, entrada, contexto):
        return NodeResult(output={'waited': True}, status='aguardando', branch='default')


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_wait_node_registrado():
    assert tipo_por_slug('_test_wait') is not None


def test_fluxo_linear_passa_dados_entre_nos():
    fluxo = {
        'inicio': 'n1',
        'nodes': {
            'n1': {'tipo': 'set_fields', 'config': {'campo': 'nome', 'valor': 'Lucas'}},
            'n2': {'tipo': 'set_fields', 'config': {'campo': 'saudacao', 'valor': 'Oi {{var.nome}}'}},
        },
        'conexoes': [{'de': 'n1', 'para': 'n2', 'saida': 'sucesso'}],
    }
    ctx = _ctx()
    res = executar_fluxo(fluxo, ctx)
    assert res.status == 'completado'
    assert ctx.variaveis['saudacao'] == 'Oi Lucas'
    assert [p.handle for p in res.passos] == ['n1', 'n2']


def test_referencia_output_de_no_anterior():
    with mock.patch('apps.automacao.nodes.http_request.requests.request') as mq:
        mq.return_value = _FakeResp(200, {'Content-Type': 'application/json'}, b'{"token":"abc"}')
        fluxo = {
            'inicio': 'h',
            'nodes': {
                'h': {'tipo': 'http_request', 'config': {'url': 'http://1.1.1.1/'}},
                's': {'tipo': 'set_fields', 'config': {'campo': 'tk', 'valor': '{{nodes.h.body.token}}'}},
            },
            'conexoes': [{'de': 'h', 'para': 's', 'saida': 'sucesso'}],
        }
        ctx = _ctx()
        res = executar_fluxo(fluxo, ctx)
    assert res.status == 'completado'
    assert ctx.variaveis['tk'] == 'abc'


def test_branch_erro_segue_aresta_de_erro():
    with mock.patch('apps.automacao.nodes.http_request.requests.request') as mq:
        mq.return_value = _FakeResp(500, body=b'{}')
        fluxo = {
            'inicio': 'h',
            'nodes': {
                'h': {'tipo': 'http_request', 'config': {'url': 'http://1.1.1.1/'}},
                'trata': {'tipo': 'set_fields', 'config': {'campo': 'falhou', 'valor': 'sim'}},
            },
            'conexoes': [{'de': 'h', 'para': 'trata', 'saida': 'erro'}],
        }
        ctx = _ctx()
        res = executar_fluxo(fluxo, ctx)
    assert res.status == 'completado'
    assert ctx.variaveis['falhou'] == 'sim'


def test_erro_sem_aresta_de_tratamento_falha():
    with mock.patch('apps.automacao.nodes.http_request.requests.request') as mq:
        mq.return_value = _FakeResp(500, body=b'{}')
        fluxo = {
            'inicio': 'h',
            'nodes': {'h': {'tipo': 'http_request', 'config': {'url': 'http://1.1.1.1/'}}},
            'conexoes': [],
        }
        res = executar_fluxo(fluxo, _ctx())
    assert res.status == 'erro'


def test_pausa_e_retoma():
    fluxo = {
        'inicio': 'w',
        'nodes': {
            'w': {'tipo': '_test_wait', 'config': {}},
            'depois': {'tipo': 'set_fields', 'config': {'campo': 'ok', 'valor': 'sim'}},
        },
        'conexoes': [{'de': 'w', 'para': 'depois', 'saida': 'default'}],
    }
    ctx = _ctx()
    res = executar_fluxo(fluxo, ctx)
    assert res.status == 'aguardando'
    assert res.aguardando['no_pausado'] == 'w'
    assert 'estado' in res.aguardando
    # retoma a partir do nó seguinte ao pausado
    from apps.automacao.runtime import _proxima
    proximo = _proxima(fluxo, 'w', 'default')
    res2 = executar_fluxo(fluxo, ctx, inicio=proximo)
    assert res2.status == 'completado'
    assert ctx.variaveis['ok'] == 'sim'


def test_loop_guard():
    fluxo = {
        'inicio': 'a',
        'nodes': {'a': {'tipo': 'set_fields', 'config': {'campo': 'x', 'valor': '1'}}},
        'conexoes': [{'de': 'a', 'para': 'a', 'saida': 'sucesso'}],
    }
    res = executar_fluxo(fluxo, _ctx(), max_passos=10)
    assert res.status == 'erro'
    assert 'loop' in res.erro


def test_validar_fluxo_detecta_problemas():
    assert validar_fluxo({'inicio': 'x', 'nodes': {}}) != []
    assert validar_fluxo({
        'inicio': 'a',
        'nodes': {'a': {'tipo': 'inexistente'}},
        'conexoes': [],
    }) != []


def test_fluxo_invalido_levanta():
    import pytest
    with pytest.raises(FluxoInvalido):
        executar_fluxo({'inicio': 'x', 'nodes': {}}, _ctx())


@registrar
class _BoomNode(BaseNode):
    """Nó de teste que estoura exceção (valida o F3)."""
    tipo = "_test_boom"
    label = "Boom"

    def executar(self, config, entrada, contexto):
        raise RuntimeError("estourou")


def test_no_que_estoura_vira_erro_controlado():
    fluxo = {'inicio': 'b', 'nodes': {'b': {'tipo': '_test_boom'}}, 'conexoes': []}
    res = executar_fluxo(fluxo, _ctx())
    assert res.status == 'erro'
    assert 'estourou' in res.erro  # não propaga a exceção, vira erro do nó


def test_validacao_rejeita_saida_inexistente():
    # http_request só tem sucesso/erro — usar 'foo' deve ser barrado
    fluxo = {
        'inicio': 'h',
        'nodes': {
            'h': {'tipo': 'http_request', 'config': {'url': 'http://1.1.1.1/'}},
            's': {'tipo': 'set_fields', 'config': {'campo': 'x', 'valor': '1'}},
        },
        'conexoes': [{'de': 'h', 'para': 's', 'saida': 'foo'}],
    }
    erros = validar_fluxo(fluxo)
    assert any('foo' in e for e in erros)
