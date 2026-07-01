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


# --- listar faturas (read) -----------------------------------------------
def test_faturas_registrado_e_exige_cpf():
    no = tipo_por_slug('hubsoft_listar_faturas')
    assert no is not None
    assert no.validar_config({})
    assert not no.validar_config({'cpf_cnpj': '123'})


def test_faturas_ok():
    no = tipo_por_slug('hubsoft_listar_faturas')
    ctx = _ctx(lead=SimpleNamespace(cpf_cnpj='12345678900'))
    with mock.patch('apps.automacao.nodes.hubsoft_listar_faturas.listar_faturas',
                    return_value=[{'id': 1}, {'id': 2}]) as m:
        res = no.executar({'cpf_cnpj': '{{lead.cpf_cnpj}}', 'apenas_pendente': True}, {}, ctx)
    assert res.branch == 'sucesso'
    assert res.output['total'] == 2
    assert m.call_args.args[1] == '12345678900'
    assert m.call_args.kwargs['apenas_pendente'] is True


# --- planos por CEP (read) -----------------------------------------------
def test_planos_registrado_e_exige_cep():
    no = tipo_por_slug('hubsoft_planos_cep')
    assert no is not None
    assert no.validar_config({})
    assert not no.validar_config({'cep': '13730000'})


def test_planos_ok():
    no = tipo_por_slug('hubsoft_planos_cep')
    ctx = _ctx(lead=SimpleNamespace(cep='13730000'))
    with mock.patch('apps.automacao.nodes.hubsoft_planos_cep.listar_planos_por_cep',
                    return_value=[{'plano': 'A'}]) as m:
        res = no.executar({'cep': '{{lead.cep}}'}, {}, ctx)
    assert res.branch == 'sucesso' and res.output['total'] == 1
    assert m.call_args.args[1] == '13730000'


# --- seletor de credencial (picker) --------------------------------------
def _tem_campo_conta(no):
    return any(c.get('nome') == 'integracao_id' and c.get('fonte') == 'integracoes_hubsoft'
               for c in no.campos_config())


def test_fonte_integracoes_hubsoft_registrada():
    from apps.automacao.opcoes import FONTES
    assert 'integracoes_hubsoft' in FONTES


def test_todos_nodes_hubsoft_tem_campo_conta():
    # amostra das 2 famílias (base HubsoftNode + BaseNode próprio) e do catálogo (sem _campos_extra)
    for t in ('hubsoft_criar_contrato', 'hubsoft_viabilidade_endereco', 'hubsoft_listar_servicos',
              'hubsoft_consultar_cliente', 'hubsoft_listar_faturas', 'hubsoft_planos_cep',
              'hubsoft_sincronizar_prospecto'):
        assert _tem_campo_conta(tipo_por_slug(t)), t


def test_base_resolve_integ_id_escolhido():
    no = tipo_por_slug('hubsoft_listar_servicos')
    svc = mock.Mock()
    svc.listar_servicos.return_value = []
    with mock.patch('apps.automacao.nodes.hubsoft_base.hubsoft_do_tenant', return_value=svc) as m:
        no.executar({'integracao_id': '7'}, {}, _ctx())
    assert m.call_args.args[1] == '7'  # integ_id chega no resolvedor


def test_familia2_thread_integ_id():
    no = tipo_por_slug('hubsoft_consultar_cliente')
    with mock.patch('apps.automacao.nodes.hubsoft_consultar_cliente.consultar_cliente',
                    return_value={}) as m:
        no.executar({'cpf_cnpj': '123', 'integracao_id': '9'}, {}, _ctx())
    assert m.call_args.kwargs['integ_id'] == '9'
