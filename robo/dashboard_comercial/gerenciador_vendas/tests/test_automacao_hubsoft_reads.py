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


# --- batch 2: cliente-scoped --------------------------------------------
def test_batch2_registrados():
    for t in ('hubsoft_listar_atendimentos_cliente', 'hubsoft_listar_os_cliente',
              'hubsoft_extrato_conexao', 'hubsoft_listar_renegociacoes',
              'hubsoft_simular_renegociacao'):
        assert tipo_por_slug(t) is not None, t


def test_atendimentos_exige_identificacao():
    no = tipo_por_slug('hubsoft_listar_atendimentos_cliente')
    assert no.validar_config({})  # nenhuma id
    assert not no.validar_config({'cpf_cnpj': '123'})


def test_atendimentos_chama_com_ident():
    no = tipo_por_slug('hubsoft_listar_atendimentos_cliente')
    svc = mock.Mock()
    svc.listar_atendimentos_cliente.return_value = [{'id': 1}]
    ctx = _ctx(lead=SimpleNamespace(cpf_cnpj='12345678900'))
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'cpf_cnpj': '{{lead.cpf_cnpj}}', 'limit': '5'}, {}, ctx)
    assert res.branch == 'sucesso' and res.output['total'] == 1
    kw = svc.listar_atendimentos_cliente.call_args.kwargs
    assert kw['cpf_cnpj'] == '12345678900' and kw['limit'] == 5


def test_extrato_exige_termo():
    no = tipo_por_slug('hubsoft_extrato_conexao')
    assert no.validar_config({})
    assert not no.validar_config({'termo_busca': 'login123'})


def test_extrato_chama_service():
    no = tipo_por_slug('hubsoft_extrato_conexao')
    svc = mock.Mock()
    svc.verificar_extrato_conexao.return_value = []
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'busca': 'mac', 'termo_busca': 'AA:BB', 'limit': '10'}, {}, _ctx())
    assert res.branch == 'sucesso'
    kw = svc.verificar_extrato_conexao.call_args.kwargs
    assert kw['busca'] == 'mac' and kw['termo_busca'] == 'AA:BB' and kw['limit'] == 10


def test_renegociacoes_extrai_lista():
    no = tipo_por_slug('hubsoft_listar_renegociacoes')
    svc = mock.Mock()
    svc.listar_renegociacoes.return_value = {'paginacao': {}, 'renegociacoes': [{'id': 1}, {'id': 2}]}
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'cpf_cnpj': '123'}, {}, _ctx())
    assert res.branch == 'sucesso' and res.output == {'renegociacoes': [{'id': 1}, {'id': 2}], 'total': 2}


def test_simular_exige_campos_e_parseia_ids():
    no = tipo_por_slug('hubsoft_simular_renegociacao')
    assert no.validar_config({})  # faltam ids/parcelas/vencimento/cliente
    svc = mock.Mock()
    svc.simular_renegociacao.return_value = {'parcelas': []}
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar(
            {'ids_faturas': '123, 124 ; 125', 'quantidade_parcelas': '3',
             'vencimento': '2026-07-10', 'cpf_cnpj': '999'}, {}, _ctx())
    assert res.branch == 'sucesso'
    kw = svc.simular_renegociacao.call_args.kwargs
    assert kw['ids_faturas'] == [123, 124, 125]
    assert kw['quantidade_parcelas'] == 3 and kw['vencimento'] == '2026-07-10'
