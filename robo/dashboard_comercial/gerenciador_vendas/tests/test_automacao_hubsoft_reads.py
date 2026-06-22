"""Nós HubSoft read (catálogo + viabilidade) — unit (sem rede; service mockado)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_PATCH = 'apps.automacao.nodes.hubsoft_base.hubsoft_do_tenant'


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrados():
    for t in ('hubsoft_listar_servicos', 'hubsoft_listar_vencimentos',
              'hubsoft_listar_modelos_contrato', 'hubsoft_viabilidade_endereco',
              'hubsoft_viabilidade_coords'):
        assert tipo_por_slug(t) is not None, t


def test_sem_integracao_vira_erro():
    no = tipo_por_slug('hubsoft_listar_servicos')
    with mock.patch(_PATCH, return_value=None):
        res = no.executar({}, {}, _ctx())
    assert res.branch == 'erro' and 'HubSoft' in res.erro


def test_listar_servicos_ok():
    no = tipo_por_slug('hubsoft_listar_servicos')
    svc = mock.Mock()
    svc.listar_servicos.return_value = [{'id': 1}, {'id': 2}]
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({}, {}, _ctx())
    assert res.branch == 'sucesso'
    assert res.output == {'servicos': [{'id': 1}, {'id': 2}], 'total': 2}


def test_viabilidade_endereco_exige_campos():
    no = tipo_por_slug('hubsoft_viabilidade_endereco')
    assert no.validar_config({})
    assert not no.validar_config(
        {'endereco': 'R X', 'numero': '1', 'bairro': 'B', 'cidade': 'C', 'estado': 'SP'})


def test_viabilidade_endereco_chama_service():
    no = tipo_por_slug('hubsoft_viabilidade_endereco')
    svc = mock.Mock()
    svc.consultar_viabilidade_endereco.return_value = {'caixas': []}
    ctx = _ctx(lead=SimpleNamespace(cidade='Mococa'))
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar(
            {'endereco': 'R X', 'numero': '1', 'bairro': 'B',
             'cidade': '{{lead.cidade}}', 'estado': 'sp', 'raio': '300'}, {}, ctx)
    assert res.branch == 'sucesso'
    assert res.output == {'viabilidade': {'caixas': []}}
    kw = svc.consultar_viabilidade_endereco.call_args.kwargs
    assert kw['cidade'] == 'Mococa' and kw['raio'] == 300 and kw['endereco'] == 'R X'


def test_viabilidade_coords_chama_service():
    no = tipo_por_slug('hubsoft_viabilidade_coords')
    svc = mock.Mock()
    svc.consultar_viabilidade_coords.return_value = {}
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'latitude': '-21.4', 'longitude': '-47.0'}, {}, _ctx())
    assert res.branch == 'sucesso'
    kw = svc.consultar_viabilidade_coords.call_args.kwargs
    assert kw['latitude'] == -21.4 and kw['longitude'] == -47.0
