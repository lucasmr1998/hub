"""Testes do nó `enviar_venda_whatsapp` (mock do service, sem DB/rede)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_SVC = 'apps.automacao.nodes.enviar_venda_whatsapp.enviar_venda'


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_registrado():
    assert tipo_por_slug('enviar_venda_whatsapp') is not None


def test_tem_picker_uazapi():
    campos = tipo_por_slug('enviar_venda_whatsapp').campos_config()
    assert any(c.get('nome') == 'integracao_id' and c.get('fonte') == 'integracoes_uazapi' for c in campos)


def test_exige_telefone():
    no = tipo_por_slug('enviar_venda_whatsapp')
    assert no.validar_config({})
    assert not no.validar_config({'telefone': '5511999'})


@mock.patch(_SVC)
def test_envia_chama_service_com_integ_id(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (True, {'docs_enviados': 2, 'motivo': None})
    res = tipo_por_slug('enviar_venda_whatsapp').executar(
        {'telefone': '{{var.tel}}', 'integracao_id': '9'}, {},
        _ctx(oportunidade=op, variaveis={'tel': '5553981521653'}))
    assert res.branch == 'sucesso'
    assert res.output['enviou'] is True and res.output['docs_enviados'] == 2
    assert mock_acao.call_args.kwargs['telefone'] == '5553981521653'
    assert mock_acao.call_args.kwargs['integ_id'] == '9'


@mock.patch(_SVC)
def test_idempotente_nao_enviou(mock_acao):
    op = SimpleNamespace(pk=7)
    mock_acao.return_value = (False, {'docs_enviados': 0, 'motivo': 'ja enviado anteriormente'})
    res = tipo_por_slug('enviar_venda_whatsapp').executar({'telefone': '5511999'}, {}, _ctx(oportunidade=op))
    assert res.branch == 'sucesso' and res.output['enviou'] is False


def test_sem_oportunidade_vira_erro():
    res = tipo_por_slug('enviar_venda_whatsapp').executar({'telefone': '5511999'}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'oportunidade' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_falha_do_service_vira_erro(mock_acao):
    mock_acao.side_effect = ValueError('telefone vazio.')
    res = tipo_por_slug('enviar_venda_whatsapp').executar(
        {'telefone': '5511999'}, {}, _ctx(oportunidade=SimpleNamespace(pk=7)))
    assert res.branch == 'erro'
