"""
Testes dos nós de WhatsApp/Uazapi.

Sem DB nem rede: `uazapi_do_tenant` é mockado (retorna um service falso ou None).
"""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def test_nodes_registrados():
    for t in ('whatsapp_texto', 'whatsapp_midia', 'whatsapp_presenca'):
        assert tipo_por_slug(t) is not None


@mock.patch('apps.automacao.nodes.whatsapp.uazapi_do_tenant')
def test_enviar_texto_resolve_template_e_chama_service(mock_uaz):
    fake = mock.Mock()
    mock_uaz.return_value = fake
    res = tipo_por_slug('whatsapp_texto').executar(
        {'telefone': '{{var.tel}}', 'mensagem': 'Oi {{var.n}}'}, {},
        _ctx(variaveis={'tel': '5589999', 'n': 'Ana'}),
    )
    assert res.branch == 'sucesso'
    fake.enviar_texto.assert_called_once_with('5589999', 'Oi Ana')


@mock.patch('apps.automacao.nodes.whatsapp.uazapi_do_tenant')
def test_sem_integracao_vira_erro(mock_uaz):
    mock_uaz.return_value = None
    res = tipo_por_slug('whatsapp_texto').executar({'telefone': '123'}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'Uazapi' in res.erro


@mock.patch('apps.automacao.nodes.whatsapp.uazapi_do_tenant')
def test_falha_do_service_vira_erro(mock_uaz):
    fake = mock.Mock()
    fake.enviar_texto.side_effect = RuntimeError('500')
    mock_uaz.return_value = fake
    res = tipo_por_slug('whatsapp_texto').executar({'telefone': '123', 'mensagem': 'x'}, {}, _ctx())
    assert res.branch == 'erro'


@mock.patch('apps.automacao.nodes.whatsapp.uazapi_do_tenant')
def test_midia(mock_uaz):
    fake = mock.Mock()
    mock_uaz.return_value = fake
    res = tipo_por_slug('whatsapp_midia').executar(
        {'telefone': '123', 'url': 'http://x/img.png', 'tipo': 'image', 'legenda': 'oi'}, {}, _ctx())
    assert res.branch == 'sucesso'
    fake.enviar_midia.assert_called_once()


def test_validar_config_texto_sem_telefone():
    assert tipo_por_slug('whatsapp_texto').validar_config({}) != []
