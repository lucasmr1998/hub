"""Nó `acao_comercial` — unit (sem DB; registry de ações mockado)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_DICT = 'apps.comercial.crm.services.automacao_pipeline._EXECUTORES_ACAO'


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrado():
    assert tipo_por_slug('acao_comercial') is not None


def test_validar_exige_tipo():
    no = tipo_por_slug('acao_comercial')
    assert no.validar_config({})
    assert not no.validar_config({'tipo_acao': 'criar_venda'})


def test_sem_oportunidade_erro():
    no = tipo_por_slug('acao_comercial')
    res = no.executar({'tipo_acao': 'criar_venda'}, {}, _ctx())
    assert res.branch == 'erro'


def test_executa_e_resolve_config():
    no = tipo_por_slug('acao_comercial')
    fake = mock.Mock(return_value=True)
    with mock.patch.dict(_DICT, {'criar_venda': fake}, clear=False):
        res = no.executar(
            {'tipo_acao': 'criar_venda', 'config': {'x': '{{var.y}}'}},
            {}, _ctx(oportunidade=SimpleNamespace(pk=1), variaveis={'y': 'Z'}))
    assert res.branch == 'sucesso' and res.output == {'ok': True, 'efetivou': True}
    op_arg, cfg_arg = fake.call_args.args
    assert op_arg.pk == 1 and cfg_arg == {'x': 'Z'}


def test_idempotente_false():
    no = tipo_por_slug('acao_comercial')
    fake = mock.Mock(return_value=False)
    with mock.patch.dict(_DICT, {'criar_venda': fake}, clear=False):
        res = no.executar({'tipo_acao': 'criar_venda'}, {}, _ctx(oportunidade=SimpleNamespace(pk=1)))
    assert res.branch == 'sucesso' and res.output['efetivou'] is False


def test_acao_desconhecida_erro():
    no = tipo_por_slug('acao_comercial')
    res = no.executar({'tipo_acao': 'inexistente_xyz'}, {}, _ctx(oportunidade=SimpleNamespace(pk=1)))
    assert res.branch == 'erro'
