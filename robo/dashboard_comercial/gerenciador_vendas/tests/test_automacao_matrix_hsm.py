"""Nó `matrix_hsm` — unit (sem DB, sem rede; matrix_do_tenant mockado)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrado():
    assert tipo_por_slug('matrix_hsm') is not None


def test_validar_exige_campos():
    no = tipo_por_slug('matrix_hsm')
    assert no.validar_config({})  # faltam cod_conta/hsm/telefone
    assert not no.validar_config({'cod_conta': '5', 'hsm': '11', 'telefone': '5511999'})


def test_sem_integracao_vira_erro():
    no = tipo_por_slug('matrix_hsm')
    with mock.patch('apps.automacao.nodes.matrix_hsm.matrix_do_tenant', return_value=None):
        res = no.executar({'cod_conta': '5', 'hsm': '11', 'telefone': '5511999'}, {}, _ctx())
    assert res.branch == 'erro' and 'Matrix' in res.erro


def test_disparo_ok_resolve_template_e_chama_service():
    no = tipo_por_slug('matrix_hsm')
    ctx = _ctx(lead=SimpleNamespace(nome='João'), variaveis={'tel': '5511999', 'n': 'João'})
    svc = mock.Mock()
    svc.enviar_hsm.return_value = {'cod_error': 0, 'cod_atendimento': 77}
    with mock.patch('apps.automacao.nodes.matrix_hsm.matrix_do_tenant', return_value=svc):
        res = no.executar({
            'cod_conta': '5', 'hsm': '11', 'telefone': '{{var.tel}}',
            'nome': '{{lead.nome}}', 'variaveis': {'1': '{{var.n}}'}, 'tipo_envio': '2',
        }, {}, ctx)
    assert res.branch == 'sucesso'
    assert res.output == {'ok': True, 'cod_atendimento': 77}
    kwargs = svc.enviar_hsm.call_args.kwargs
    assert kwargs['cod_conta'] == 5 and kwargs['hsm'] == 11 and kwargs['tipo_envio'] == 2
    assert kwargs['contato'] == {'telefone': '5511999', 'nome': 'João'}
    assert kwargs['variaveis'] == {'1': 'João'}


def test_falha_do_service_vira_erro():
    no = tipo_por_slug('matrix_hsm')
    svc = mock.Mock()
    svc.enviar_hsm.side_effect = Exception('Token Matrix invalido')
    with mock.patch('apps.automacao.nodes.matrix_hsm.matrix_do_tenant', return_value=svc):
        res = no.executar({'cod_conta': '5', 'hsm': '11', 'telefone': '5511999'}, {}, _ctx())
    assert res.branch == 'erro' and 'Matrix' in res.erro
