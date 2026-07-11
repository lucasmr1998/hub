"""Testes do nó `reabrir_oportunidade` (mock do service, sem DB)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_SVC = 'apps.automacao.nodes.reabrir_oportunidade.reabrir_oportunidade'


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_registrado():
    assert tipo_por_slug('reabrir_oportunidade') is not None


@mock.patch(_SVC)
def test_caminho_feliz_chama_service_com_template_resolvido(mock_acao):
    op = SimpleNamespace(pk=7)
    ctx = _ctx(oportunidade=op, variaveis={'x': 'negociacao'})
    estagio = SimpleNamespace(slug='negociacao')
    mock_acao.return_value = (estagio, True)

    res = tipo_por_slug('reabrir_oportunidade').executar(
        {'estagio_slug': '{{var.x}}', 'motivo': 'Cliente retornou'}, {}, ctx)

    assert res.branch == 'sucesso'
    assert res.output == {'reaberta': True, 'estagio': 'negociacao'}
    assert mock_acao.call_args.args[0] is ctx.tenant
    kwargs = mock_acao.call_args.kwargs
    assert kwargs['oportunidade'] is op
    assert kwargs['estagio_slug'] == 'negociacao'
    assert kwargs['motivo'] == 'Cliente retornou'


@mock.patch(_SVC)
def test_idempotente_nao_reabre_devolve_sucesso_sem_reabrir(mock_acao):
    mock_acao.return_value = (None, False)
    op = SimpleNamespace(pk=7)
    res = tipo_por_slug('reabrir_oportunidade').executar(
        {'estagio_slug': 'negociacao'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso'
    assert res.output == {'reaberta': False, 'estagio': None}


def test_sem_oportunidade_vira_erro():
    res = tipo_por_slug('reabrir_oportunidade').executar({'estagio_slug': 'x'}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'oportunidade' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_falha_do_service_vira_erro(mock_acao):
    mock_acao.side_effect = ValueError('Estágio "x" não encontrado no pipeline.')
    op = SimpleNamespace(pk=7)
    res = tipo_por_slug('reabrir_oportunidade').executar({'estagio_slug': 'x'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'erro' and res.status == 'erro'
