"""Testes do nó `responder_webhook` (Respond to Webhook do n8n)."""
from types import SimpleNamespace

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='a'), **kw)


def test_registrado():
    assert tipo_por_slug('responder_webhook') is not None


def test_define_resposta_resolvendo_template():
    no = tipo_por_slug('responder_webhook')
    res = no.executar({'status': 201, 'corpo': '{"msg": "{{var.x}}"}'}, {}, _ctx(variaveis={'x': 'World'}))
    assert res.branch == 'sucesso'
    assert res.promote['_resposta_webhook'] == {'status': 201, 'corpo': '{"msg": "World"}'}


def test_status_default_200():
    no = tipo_por_slug('responder_webhook')
    res = no.executar({'corpo': 'ok'}, {}, _ctx())
    assert res.promote['_resposta_webhook']['status'] == 200
