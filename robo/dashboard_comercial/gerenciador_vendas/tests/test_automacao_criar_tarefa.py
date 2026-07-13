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
    responsavel = SimpleNamespace(get_full_name=lambda: '', username='vendedora1')
    fake = SimpleNamespace(pk=42, titulo='Follow-up: Lucas', responsavel=responsavel)
    with mock.patch('apps.automacao.nodes.criar_tarefa.criar_tarefa', return_value=fake) as m:
        res = no.executar(
            {'titulo': 'Follow-up: {{var.nome}}', 'tipo': 'followup',
             'prioridade': 'alta', 'prazo_dias': '3', 'descricao': 'Contexto: {{var.nome}}'},
            {}, ctx,
        )
    assert res.branch == 'sucesso'
    # output traz responsavel resolvido (username, sem full_name aqui) pra observabilidade
    assert res.output == {'tarefa_id': 42, 'titulo': 'Follow-up: Lucas', 'responsavel': 'vendedora1'}
    # service chamado com tenant + template resolvido + prazo convertido p/ int + descricao resolvida
    assert m.call_args.args[0] is ctx.tenant
    kwargs = m.call_args.kwargs
    assert kwargs['titulo'] == 'Follow-up: Lucas'
    assert kwargs['prioridade'] == 'alta'
    assert kwargs['prazo_dias'] == 3
    assert kwargs['descricao'] == 'Contexto: Lucas'


def test_output_usa_full_name_do_responsavel_quando_disponivel():
    no = tipo_por_slug('criar_tarefa')
    responsavel = SimpleNamespace(get_full_name=lambda: 'Vendedora Um', username='vendedora1')
    fake = SimpleNamespace(pk=7, titulo='X', responsavel=responsavel)
    with mock.patch('apps.automacao.nodes.criar_tarefa.criar_tarefa', return_value=fake):
        res = no.executar({'titulo': 'X'}, {}, _ctx())
    assert res.output['responsavel'] == 'Vendedora Um'


def test_descricao_ausente_vira_string_vazia_no_service():
    no = tipo_por_slug('criar_tarefa')
    responsavel = SimpleNamespace(get_full_name=lambda: '', username='u')
    fake = SimpleNamespace(pk=1, titulo='X', responsavel=responsavel)
    with mock.patch('apps.automacao.nodes.criar_tarefa.criar_tarefa', return_value=fake) as m:
        no.executar({'titulo': 'X'}, {}, _ctx())
    assert m.call_args.kwargs['descricao'] == ''


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
