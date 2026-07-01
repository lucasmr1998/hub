"""Testes do nó `mover_para_perdido_sem_viabilidade` (mock do service, sem DB)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_SVC = 'apps.automacao.nodes.mover_para_perdido_sem_viabilidade.mover_para_perdido_sem_viabilidade'


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_registrado():
    assert tipo_por_slug('mover_para_perdido_sem_viabilidade') is not None


@mock.patch(_SVC)
def test_move_chama_service_e_resolve_template(mock_acao):
    op = SimpleNamespace(pk=7, motivo_perda='CEP 64000 sem cobertura em Teresina/PI')
    mock_acao.return_value = (SimpleNamespace(slug='perdido'), True)
    res = tipo_por_slug('mover_para_perdido_sem_viabilidade').executar(
        {'motivo_template': 'CEP {cep} {{var.x}}'}, {},
        _ctx(oportunidade=op, variaveis={'x': 'extra'}))
    assert res.branch == 'sucesso'
    assert res.output['movido'] is True
    assert res.output['estagio'] == 'perdido'
    # o template teve {{...}} resolvido antes de ir pro service; {cep} (placeholder .format) fica pro service
    assert mock_acao.call_args.kwargs['motivo_template'] == 'CEP {cep} extra'


@mock.patch(_SVC)
def test_ja_perdido_nao_move(mock_acao):
    op = SimpleNamespace(pk=7, motivo_perda=None)
    mock_acao.return_value = (SimpleNamespace(slug='perdido'), False)
    res = tipo_por_slug('mover_para_perdido_sem_viabilidade').executar({}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso'
    assert res.output['movido'] is False


def test_sem_oportunidade_vira_erro():
    res = tipo_por_slug('mover_para_perdido_sem_viabilidade').executar({}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'oportunidade' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_falha_do_service_vira_erro(mock_acao):
    mock_acao.side_effect = ValueError('sem estagio perdido')
    op = SimpleNamespace(pk=7, motivo_perda=None)
    res = tipo_por_slug('mover_para_perdido_sem_viabilidade').executar({}, {}, _ctx(oportunidade=op))
    assert res.branch == 'erro'
