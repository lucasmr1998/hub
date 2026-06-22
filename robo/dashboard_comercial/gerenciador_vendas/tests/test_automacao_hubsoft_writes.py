"""Nós HubSoft write moderado — unit (sem rede/ERP; service mockado)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug

_PATCH = 'apps.automacao.nodes.hubsoft_base.hubsoft_do_tenant'


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrados():
    for t in ('hubsoft_criar_contrato', 'hubsoft_aceitar_contrato', 'hubsoft_efetivar_renegociacao',
              'hubsoft_abrir_atendimento_os', 'hubsoft_agendar_os', 'hubsoft_abrir_os'):
        assert tipo_por_slug(t) is not None, t


def test_sem_integracao_vira_erro():
    no = tipo_por_slug('hubsoft_agendar_os')
    with mock.patch(_PATCH, return_value=None):
        res = no.executar({'id_ordem_servico': '5'}, {}, _ctx())
    assert res.branch == 'erro' and 'HubSoft' in res.erro


def test_criar_contrato_exige_obrigatorios_e_delega():
    no = tipo_por_slug('hubsoft_criar_contrato')
    assert len(no.validar_config({})) == 5  # 5 obrigatórios
    svc = mock.Mock()
    svc.criar_contrato.return_value = {'id_cliente_servico_contrato': 7}
    ctx = _ctx(lead=SimpleNamespace(nome='ACME', cpf_cnpj='123'))
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'id_cliente_servico': '10', 'id_contrato_modelo': '2', 'id_empresa': '1',
                           'autorizacao_nome': '{{lead.nome}}', 'autorizacao_cpf': '{{lead.cpf_cnpj}}'}, {}, ctx)
    assert res.branch == 'sucesso'
    kw = svc.criar_contrato.call_args.kwargs
    assert kw['id_cliente_servico'] == 10 and kw['autorizacao_nome'] == 'ACME' and kw['autorizacao_cpf'] == '123'


def test_aceitar_contrato_delega():
    no = tipo_por_slug('hubsoft_aceitar_contrato')
    assert no.validar_config({})
    svc = mock.Mock()
    svc.aceitar_contrato.return_value = {'ok': True}
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'id_contrato': '99', 'observacao': 'ok'}, {}, _ctx())
    assert res.branch == 'sucesso'
    assert svc.aceitar_contrato.call_args.args[0] == 99
    assert svc.aceitar_contrato.call_args.kwargs['observacao'] == 'ok'


def test_efetivar_renegociacao_parseia_ids():
    no = tipo_por_slug('hubsoft_efetivar_renegociacao')
    erros = no.validar_config({})
    assert erros  # faltam obrigatórios + cliente
    svc = mock.Mock()
    svc.efetivar_renegociacao.return_value = {'ok': True}
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'ids_faturas': '1,2,3', 'quantidade_parcelas': '4',
                           'vencimento': '2026-08-01', 'id_cliente': '55'}, {}, _ctx())
    assert res.branch == 'sucesso'
    kw = svc.efetivar_renegociacao.call_args.kwargs
    assert kw['ids_faturas'] == [1, 2, 3] and kw['id_cliente'] == 55


def test_abrir_atendimento_os_delega():
    no = tipo_por_slug('hubsoft_abrir_atendimento_os')
    assert len(no.validar_config({})) == 4
    svc = mock.Mock()
    svc.abrir_atendimento_os.return_value = {'id_atendimento': 1}
    ctx = _ctx(lead=SimpleNamespace(nome='ACME', telefone='5511999'))
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'id_cliente_servico': '3', 'descricao': 'Sem sinal',
                           'nome': '{{lead.nome}}', 'telefone': '{{lead.telefone}}',
                           'ids_tecnicos': '7,8'}, {}, ctx)
    assert res.branch == 'sucesso'
    kw = svc.abrir_atendimento_os.call_args.kwargs
    assert kw['nome'] == 'ACME' and kw['telefone'] == '5511999' and kw['ids_tecnicos'] == [7, 8]


def test_abrir_os_delega():
    no = tipo_por_slug('hubsoft_abrir_os')
    assert no.validar_config({})
    svc = mock.Mock()
    svc.abrir_os.return_value = {'id_ordem_servico': 9}
    with mock.patch(_PATCH, return_value=svc):
        res = no.executar({'id_atendimento': '12', 'status': 'aberta', 'tecnicos': '3'}, {}, _ctx())
    assert res.branch == 'sucesso'
    kw = svc.abrir_os.call_args.kwargs
    assert kw['id_atendimento'] == 12 and kw['status'] == 'aberta' and kw['tecnicos'] == [3]
