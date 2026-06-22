"""Nós HubSoft — unit (sem DB, sem rede; services mockados)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


# --- sincronizar prospecto (outbound) ------------------------------------
def test_sincronizar_registrado():
    assert tipo_por_slug('hubsoft_sincronizar_prospecto') is not None


def test_sincronizar_sem_lead_vira_erro():
    no = tipo_por_slug('hubsoft_sincronizar_prospecto')
    assert no.executar({}, {}, _ctx()).branch == 'erro'


def test_sincronizar_ok():
    no = tipo_por_slug('hubsoft_sincronizar_prospecto')
    ctx = _ctx(lead=SimpleNamespace(pk=5))
    r = SimpleNamespace(ok=True, acao='criado', motivo=None, id_prospecto='123')
    with mock.patch('apps.automacao.nodes.hubsoft_sincronizar_prospecto.sincronizar_prospecto',
                    return_value=r):
        res = no.executar({}, {}, ctx)
    assert res.branch == 'sucesso'
    assert res.output == {'acao': 'criado', 'id_prospecto': '123'}


def test_sincronizar_resultado_nao_ok_vira_erro():
    no = tipo_por_slug('hubsoft_sincronizar_prospecto')
    ctx = _ctx(lead=SimpleNamespace(pk=5))
    r = SimpleNamespace(ok=False, acao='pulado', motivo='telefone vazio', id_prospecto=None)
    with mock.patch('apps.automacao.nodes.hubsoft_sincronizar_prospecto.sincronizar_prospecto',
                    return_value=r):
        res = no.executar({}, {}, ctx)
    assert res.branch == 'erro' and 'telefone' in res.erro


# --- consultar cliente (read) --------------------------------------------
def test_consultar_registrado():
    assert tipo_por_slug('hubsoft_consultar_cliente') is not None


def test_consultar_exige_cpf():
    no = tipo_por_slug('hubsoft_consultar_cliente')
    assert no.validar_config({})
    assert not no.validar_config({'cpf_cnpj': '123'})


def test_consultar_ok_resolve_template():
    no = tipo_por_slug('hubsoft_consultar_cliente')
    ctx = _ctx(lead=SimpleNamespace(cpf_cnpj='12345678900'))
    with mock.patch('apps.automacao.nodes.hubsoft_consultar_cliente.consultar_cliente',
                    return_value={'nome': 'ACME'}) as m:
        res = no.executar({'cpf_cnpj': '{{lead.cpf_cnpj}}'}, {}, ctx)
    assert res.branch == 'sucesso'
    assert res.output == {'cliente': {'nome': 'ACME'}}
    assert m.call_args.args[0] is ctx.tenant
    assert m.call_args.args[1] == '12345678900'


def test_consultar_sem_integracao_vira_erro():
    no = tipo_por_slug('hubsoft_consultar_cliente')
    with mock.patch('apps.automacao.nodes.hubsoft_consultar_cliente.consultar_cliente',
                    side_effect=ValueError('tenant sem integração HubSoft ativa')):
        res = no.executar({'cpf_cnpj': '123'}, {}, _ctx())
    assert res.branch == 'erro' and 'HubSoft' in res.erro
