"""Testes do nó `marcar_dados_custom` (mock do service, sem DB)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_SVC = 'apps.automacao.nodes.marcar_dados_custom.marcar_dados_custom'


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_registrado():
    assert tipo_por_slug('marcar_dados_custom') is not None


@mock.patch(_SVC)
def test_caminho_feliz_chama_service_com_template_resolvido(mock_acao):
    op = SimpleNamespace(pk=7)
    ctx = _ctx(oportunidade=op, variaveis={'v': 'processado'})
    mock_acao.return_value = 'processado'

    res = tipo_por_slug('marcar_dados_custom').executar(
        {'chave': 'analise_perda', 'valor': '{{var.v}}'}, {}, ctx)

    assert res.branch == 'sucesso'
    assert res.output == {'chave': 'analise_perda', 'valor': 'processado'}
    assert mock_acao.call_args.args[0] is ctx.tenant
    kwargs = mock_acao.call_args.kwargs
    assert kwargs['oportunidade'] is op
    assert kwargs['chave'] == 'analise_perda'
    assert kwargs['valor'] == 'processado'


@mock.patch(_SVC)
def test_valor_vazio_repassa_pro_service_decidir_timestamp(mock_acao):
    mock_acao.return_value = '2026-07-10T12:00:00'
    op = SimpleNamespace(pk=7)
    res = tipo_por_slug('marcar_dados_custom').executar({'chave': 'analise_perda'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso'
    assert mock_acao.call_args.kwargs['valor'] == ''


def test_sem_oportunidade_vira_erro():
    res = tipo_por_slug('marcar_dados_custom').executar({'chave': 'x'}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'oportunidade' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_falha_do_service_vira_erro(mock_acao):
    mock_acao.side_effect = ValueError('Chave não especificada.')
    op = SimpleNamespace(pk=7)
    res = tipo_por_slug('marcar_dados_custom').executar({'chave': 'x'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'erro' and res.status == 'erro'
