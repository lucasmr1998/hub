"""Testes do nó `criar_nota` (mock do service, sem DB)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_SVC = 'apps.automacao.nodes.criar_nota.criar_nota'


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_registrado():
    assert tipo_por_slug('criar_nota') is not None


@mock.patch(_SVC)
def test_caminho_feliz_chama_service_com_template_resolvido(mock_acao):
    op = SimpleNamespace(pk=7)
    ctx = _ctx(oportunidade=op, variaveis={'nome': 'Lucas'})
    nota = SimpleNamespace(pk=99, conteudo='Nota sobre Lucas')
    mock_acao.return_value = nota

    res = tipo_por_slug('criar_nota').executar({'texto': 'Nota sobre {{var.nome}}'}, {}, ctx)

    assert res.branch == 'sucesso'
    assert res.output == {'nota_id': 99, 'conteudo': 'Nota sobre Lucas'}
    assert mock_acao.call_args.args[0] is ctx.tenant
    kwargs = mock_acao.call_args.kwargs
    assert kwargs['oportunidade'] is op
    assert kwargs['texto'] == 'Nota sobre Lucas'


def test_sem_oportunidade_vira_erro():
    res = tipo_por_slug('criar_nota').executar({'texto': 'X'}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'oportunidade' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_falha_do_service_vira_erro(mock_acao):
    mock_acao.side_effect = ValueError('Nenhum autor disponível para a nota.')
    op = SimpleNamespace(pk=7)
    res = tipo_por_slug('criar_nota').executar({'texto': 'X'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'erro' and res.status == 'erro'
    assert 'autor' in (res.erro or '').lower()
