"""Testes do nó `adicionar_item_oportunidade` (mock do service, sem DB)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_SVC = 'apps.automacao.nodes.adicionar_item_oportunidade.adicionar_item_oportunidade'


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_registrado():
    assert tipo_por_slug('adicionar_item_oportunidade') is not None


@mock.patch(_SVC)
def test_vincula_chama_service(mock_acao):
    op = SimpleNamespace(pk=7)
    item = SimpleNamespace(produto=SimpleNamespace(nome='Plano 500MB'), valor_unitario='99.90')
    mock_acao.return_value = (item, True, '')
    res = tipo_por_slug('adicionar_item_oportunidade').executar(
        {'quantidade': '2'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso'
    assert res.output['criado'] is True
    assert res.output['produto'] == 'Plano 500MB'
    assert res.output['valor_unitario'] == '99.90'
    assert mock_acao.call_args.kwargs['quantidade'] == '2'


@mock.patch(_SVC)
def test_quantidade_vazia_vira_1(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (None, False, 'ja_vinculado')
    tipo_por_slug('adicionar_item_oportunidade').executar({}, {}, _ctx(oportunidade=op))
    assert mock_acao.call_args.kwargs['quantidade'] == 1


@mock.patch(_SVC)
def test_skip_nao_e_erro(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (None, False, 'produto_nao_encontrado')
    res = tipo_por_slug('adicionar_item_oportunidade').executar({}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso'
    assert res.output['criado'] is False
    assert res.output['motivo'] == 'produto_nao_encontrado'
    assert res.output['produto'] is None


def test_sem_oportunidade_vira_erro():
    res = tipo_por_slug('adicionar_item_oportunidade').executar({}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'oportunidade' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_falha_do_service_vira_erro(mock_acao):
    mock_acao.side_effect = ValueError('sem oportunidade')
    res = tipo_por_slug('adicionar_item_oportunidade').executar({}, {}, _ctx(oportunidade=SimpleNamespace(pk=7)))
    assert res.branch == 'erro'
