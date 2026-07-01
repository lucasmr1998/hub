"""Testes dos nós `gerar_contrato_hubsoft` e `assinar_contrato_hubsoft`
(mock do service, sem DB/ERP)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_GERAR = 'apps.automacao.nodes.gerar_contrato_hubsoft.gerar_contrato'
_ASSINAR = 'apps.automacao.nodes.assinar_contrato_hubsoft.assinar_contrato'


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def _tem_picker(no):
    return any(c.get('nome') == 'integracao_id' and c.get('fonte') == 'integracoes_hubsoft'
               for c in no.campos_config())


# --- gerar contrato ------------------------------------------------------
def test_gerar_registrado_e_picker():
    no = tipo_por_slug('gerar_contrato_hubsoft')
    assert no is not None and _tem_picker(no)


@mock.patch(_GERAR)
def test_gerar_ok_passa_config(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (True, {'motivo': 'ok', 'id_contrato': 555})
    res = tipo_por_slug('gerar_contrato_hubsoft').executar(
        {'id_contrato_modelo': '236', 'id_empresa': '74', 'integracao_id': '3'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso'
    assert res.output['feito'] is True and res.output['id_contrato'] == 555
    kw = mock_acao.call_args.kwargs
    assert kw['id_contrato_modelo'] == '236' and kw['id_empresa'] == '74' and kw['integ_id'] == '3'


@mock.patch(_GERAR)
def test_gerar_config_vazia_vira_none(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (False, {'motivo': 'sem_config'})
    tipo_por_slug('gerar_contrato_hubsoft').executar({}, {}, _ctx(oportunidade=op))
    kw = mock_acao.call_args.kwargs
    assert kw['id_contrato_modelo'] is None and kw['id_empresa'] is None and kw['integ_id'] is None


@mock.patch(_GERAR)
def test_gerar_skip_nao_e_erro(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (False, {'motivo': 'score_nao_aprovado'})
    res = tipo_por_slug('gerar_contrato_hubsoft').executar({}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso' and res.output['feito'] is False
    assert res.output['motivo'] == 'score_nao_aprovado'


@mock.patch(_GERAR)
def test_gerar_falha_erp_vira_erro(mock_acao):
    mock_acao.side_effect = RuntimeError('HubSoft 500')
    res = tipo_por_slug('gerar_contrato_hubsoft').executar({}, {}, _ctx(oportunidade=SimpleNamespace(pk=7)))
    assert res.branch == 'erro'


def test_gerar_sem_oportunidade_vira_erro():
    res = tipo_por_slug('gerar_contrato_hubsoft').executar({}, {}, _ctx())
    assert res.branch == 'erro' and 'oportunidade' in (res.erro or '').lower()


# --- assinar contrato ----------------------------------------------------
def test_assinar_registrado_e_picker():
    no = tipo_por_slug('assinar_contrato_hubsoft')
    assert no is not None and _tem_picker(no)


@mock.patch(_ASSINAR)
def test_assinar_ok_passa_flag(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (True, {'motivo': 'ok', 'id_contrato': 9, 'servico_ativado': True})
    res = tipo_por_slug('assinar_contrato_hubsoft').executar(
        {'ativar_servico_apos_aceite': True, 'integracao_id': '3'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso' and res.output['servico_ativado'] is True
    kw = mock_acao.call_args.kwargs
    assert kw['ativar_servico_apos_aceite'] is True and kw['integ_id'] == '3'


@mock.patch(_ASSINAR)
def test_assinar_skip_nao_e_erro(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (False, {'motivo': 'ja_aceito'})
    res = tipo_por_slug('assinar_contrato_hubsoft').executar({}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso' and res.output['feito'] is False and res.output['motivo'] == 'ja_aceito'


@mock.patch(_ASSINAR)
def test_assinar_falha_erp_vira_erro(mock_acao):
    mock_acao.side_effect = RuntimeError('HubSoft timeout')
    res = tipo_por_slug('assinar_contrato_hubsoft').executar({}, {}, _ctx(oportunidade=SimpleNamespace(pk=7)))
    assert res.branch == 'erro'


def test_assinar_sem_oportunidade_vira_erro():
    res = tipo_por_slug('assinar_contrato_hubsoft').executar({}, {}, _ctx())
    assert res.branch == 'erro' and 'oportunidade' in (res.erro or '').lower()
