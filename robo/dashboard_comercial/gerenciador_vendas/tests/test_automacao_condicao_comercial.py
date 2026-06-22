"""Nó `condicao_comercial` — unit (sem DB; registry de condições mockado)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_PATCH = 'apps.comercial.crm.services.automacao_condicoes.tipo_por_slug'


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrado():
    assert tipo_por_slug('condicao_comercial') is not None


def test_validar_exige_tipo_e_operador():
    no = tipo_por_slug('condicao_comercial')
    assert len(no.validar_config({})) == 2
    assert not no.validar_config({'tipo_condicao': 'tag', 'operador': 'igual'})


def test_sem_oportunidade_vai_false():
    no = tipo_por_slug('condicao_comercial')
    res = no.executar({'tipo_condicao': 'tag', 'operador': 'existe'}, {}, _ctx())
    assert res.branch == 'false' and res.output['resultado'] is False


def test_avalia_true_chama_registry():
    no = tipo_por_slug('condicao_comercial')
    cond = mock.Mock()
    cond.avaliar.return_value = True
    with mock.patch(_PATCH, return_value=cond):
        res = no.executar({'tipo_condicao': 'tag', 'operador': 'igual', 'valor': 'vip'},
                          {}, _ctx(oportunidade=SimpleNamespace(pk=1)))
    assert res.branch == 'true' and res.output == {'resultado': True}
    cond.coletar_contexto.assert_called_once()
    args = cond.avaliar.call_args.args
    assert args[0] == 'igual' and args[1] == 'vip'


def test_avalia_false():
    no = tipo_por_slug('condicao_comercial')
    cond = mock.Mock()
    cond.avaliar.return_value = False
    with mock.patch(_PATCH, return_value=cond):
        res = no.executar({'tipo_condicao': 'tag', 'operador': 'igual'},
                          {}, _ctx(oportunidade=SimpleNamespace(pk=1)))
    assert res.branch == 'false'


def test_condicao_que_estoura_vira_false():
    no = tipo_por_slug('condicao_comercial')
    cond = mock.Mock()
    cond.coletar_contexto.side_effect = RuntimeError('boom')
    with mock.patch(_PATCH, return_value=cond):
        res = no.executar({'tipo_condicao': 'tag', 'operador': 'igual'},
                          {}, _ctx(oportunidade=SimpleNamespace(pk=1)))
    assert res.branch == 'false' and 'boom' in res.output['erro']
