"""Testes do nó `definir_motivo_perda` (mock do service, sem DB)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_SVC = 'apps.automacao.nodes.definir_motivo_perda.definir_motivo_perda'


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_registrado():
    assert tipo_por_slug('definir_motivo_perda') is not None


@mock.patch(_SVC)
def test_caminho_feliz_chama_service_com_template_resolvido(mock_acao):
    op = SimpleNamespace(pk=7)
    ctx = _ctx(oportunidade=op, variaveis={'motivo_ia': 'Preco alto'})
    motivo = SimpleNamespace(pk=3, nome='Preco alto')
    mock_acao.return_value = (motivo, True)

    res = tipo_por_slug('definir_motivo_perda').executar(
        {'motivo_nome': '{{var.motivo_ia}}', 'texto': 'Cliente achou caro'}, {}, ctx)

    assert res.branch == 'sucesso'
    assert res.output == {'alterou': True, 'motivo': 'Preco alto'}
    assert mock_acao.call_args.args[0] is ctx.tenant
    kwargs = mock_acao.call_args.kwargs
    assert kwargs['oportunidade'] is op
    assert kwargs['motivo_nome'] == 'Preco alto'
    assert kwargs['texto'] == 'Cliente achou caro'
    # somente_se_vazio ausente na config -> default True chega no service
    assert kwargs['somente_se_vazio'] is True


@mock.patch(_SVC)
def test_somente_se_vazio_false_explicito_chega_no_service(mock_acao):
    op = SimpleNamespace(pk=7)
    motivo = SimpleNamespace(pk=3, nome='Preco alto')
    mock_acao.return_value = (motivo, True)

    res = tipo_por_slug('definir_motivo_perda').executar(
        {'motivo_nome': 'Preco alto', 'somente_se_vazio': False}, {}, _ctx(oportunidade=op))

    assert res.branch == 'sucesso'
    assert mock_acao.call_args.kwargs['somente_se_vazio'] is False


def test_sem_oportunidade_vira_erro():
    res = tipo_por_slug('definir_motivo_perda').executar({'motivo_nome': 'X'}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'oportunidade' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_falha_do_service_vira_erro(mock_acao):
    mock_acao.side_effect = ValueError('Motivo de perda "X" não encontrado. Disponíveis: preco, timing')
    op = SimpleNamespace(pk=7)
    res = tipo_por_slug('definir_motivo_perda').executar({'motivo_nome': 'X'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'erro' and res.status == 'erro'
    assert 'encontrado' in (res.erro or '').lower()
