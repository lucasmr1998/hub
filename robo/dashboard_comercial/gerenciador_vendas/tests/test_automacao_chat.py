"""Testes do nó `chat` (gatilho de teste estilo n8n)."""
from types import SimpleNamespace

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='a'), **kw)


def test_chat_registrado_e_trigger():
    no = tipo_por_slug('chat')
    assert no is not None
    assert no.is_trigger is True


def test_chat_repassa_conteudo():
    no = tipo_por_slug('chat')
    res = no.executar({}, {}, _ctx(variaveis={'conteudo': 'oi, deu erro'}))
    assert res.branch == 'default'
    assert res.output['conteudo'] == 'oi, deu erro'
