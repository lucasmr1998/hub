"""Nó `notificacao_sistema` — unit (sem DB; service mockado)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrado():
    assert tipo_por_slug('notificacao_sistema') is not None


def test_validar_config_exige_mensagem():
    no = tipo_por_slug('notificacao_sistema')
    assert no.validar_config({})
    assert not no.validar_config({'mensagem': 'oi'})


def test_executar_resolve_template_e_chama_service():
    no = tipo_por_slug('notificacao_sistema')
    ctx = _ctx(variaveis={'nome': 'Lucas'})
    with mock.patch('apps.automacao.nodes.notificacao_sistema.notificar',
                    return_value=SimpleNamespace(pk=7)) as m:
        res = no.executar(
            {'titulo': 'Lead {{var.nome}}', 'mensagem': 'Olá {{var.nome}}'}, {}, ctx,
        )
    assert res.branch == 'sucesso'
    assert res.output == {'notificacao_id': 7}
    assert m.call_args.args[0] is ctx.tenant
    assert m.call_args.kwargs['titulo'] == 'Lead Lucas'
    assert m.call_args.kwargs['mensagem'] == 'Olá Lucas'


def test_mensagem_vazia_vira_erro():
    no = tipo_por_slug('notificacao_sistema')
    res = no.executar({'mensagem': '   '}, {}, _ctx())
    assert res.branch == 'erro'


def test_tipo_nao_cadastrado_vira_erro():
    no = tipo_por_slug('notificacao_sistema')
    with mock.patch('apps.automacao.nodes.notificacao_sistema.notificar', return_value=None):
        res = no.executar({'mensagem': 'x'}, {}, _ctx())
    assert res.branch == 'erro' and res.status == 'erro'
