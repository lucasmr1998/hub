"""Nó `criar_tarefa` — unit (sem DB; service mockado)."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrado():
    assert tipo_por_slug('criar_tarefa') is not None


def test_validar_config_exige_titulo():
    no = tipo_por_slug('criar_tarefa')
    assert no.validar_config({})
    assert not no.validar_config({'titulo': 'X'})


def test_executar_resolve_template_e_chama_service():
    no = tipo_por_slug('criar_tarefa')
    ctx = _ctx(variaveis={'nome': 'Lucas'})
    fake = SimpleNamespace(pk=42, titulo='Follow-up: Lucas')
    with mock.patch('apps.automacao.nodes.criar_tarefa.criar_tarefa', return_value=fake) as m:
        res = no.executar(
            {'titulo': 'Follow-up: {{var.nome}}', 'tipo': 'followup',
             'prioridade': 'alta', 'prazo_dias': '3'},
            {}, ctx,
        )
    assert res.branch == 'sucesso'
    assert res.output == {'tarefa_id': 42, 'titulo': 'Follow-up: Lucas'}
    # service chamado com tenant + template resolvido + prazo convertido p/ int
    assert m.call_args.args[0] is ctx.tenant
    kwargs = m.call_args.kwargs
    assert kwargs['titulo'] == 'Follow-up: Lucas'
    assert kwargs['prioridade'] == 'alta'
    assert kwargs['prazo_dias'] == 3


def test_titulo_vazio_vira_erro():
    no = tipo_por_slug('criar_tarefa')
    res = no.executar({'titulo': '   '}, {}, _ctx())
    assert res.branch == 'erro'


def test_falha_do_service_vira_branch_erro():
    no = tipo_por_slug('criar_tarefa')
    with mock.patch('apps.automacao.nodes.criar_tarefa.criar_tarefa',
                    side_effect=ValueError('sem responsável')):
        res = no.executar({'titulo': 'X'}, {}, _ctx())
    assert res.branch == 'erro' and res.status == 'erro' and 'responsável' in res.erro
