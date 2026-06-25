"""
Testes das tools do agente (D3): registry/schema, dispatch (teto, tenant-safe),
loop de tool-calling e o nó ia_agente usando tools.

Sem DB nem rede: LogSistema, o nó delegado, `requests.post` e o Agente são mockados.
"""
import json
from types import SimpleNamespace
from unittest import mock

import pytest

from apps.automacao.services import ia_tools
from apps.automacao.services.ia import chamar_llm_com_tools
from apps.automacao.nodes import Contexto, tipo_por_slug


def test_schema_openai_so_habilitadas():
    schema = ia_tools.schema_openai(['registrar_feedback', 'inexistente'])
    assert [s['function']['name'] for s in schema] == ['registrar_feedback']
    fn = schema[0]['function']
    assert 'nota' in fn['parameters']['properties']
    assert fn['parameters']['required'] == ['nota']


def test_despachar_desconhecida_nao_levanta():
    assert 'desconhecida' in ia_tools.despachar('nope', {}, SimpleNamespace(tenant=1))


def test_cap_trunca_output():
    s = ia_tools._cap('x' * 5000)
    assert len(s) <= ia_tools.TETO_RESULTADO + 20
    assert s.endswith('(truncado)')


def test_registrar_feedback_grava_logsistema_tenant_safe():
    ctx = SimpleNamespace(tenant=SimpleNamespace(pk=7), lead=SimpleNamespace(pk=42))
    with mock.patch('apps.sistema.models.LogSistema') as MLog:
        out = ia_tools.despachar('registrar_feedback', {'nota': 9, 'comentario': 'ótimo'}, ctx)
    assert 'feedback' in out.lower()
    MLog.objects.create.assert_called_once()
    kw = MLog.objects.create.call_args.kwargs
    assert kw['tenant'] is ctx.tenant
    assert kw['entidade_id'] == 42
    assert kw['dados_extras']['nota'] == 9


def test_criar_oportunidade_delega_ao_no_e_pina_pipeline():
    ctx = SimpleNamespace(tenant=SimpleNamespace(pk=1), lead=SimpleNamespace(pk=5))
    fake_no = mock.Mock()
    fake_no.executar.return_value = SimpleNamespace(branch='sucesso', output={'titulo': 'Plano X'}, erro=None)
    with mock.patch('apps.automacao.nodes.tipo_por_slug', return_value=fake_no):
        out = ia_tools.despachar('criar_oportunidade', {'titulo': 'Plano X', 'valor': 100}, ctx)
    assert 'oportunidade criada' in out
    cfg = fake_no.executar.call_args[0][0]
    assert cfg['titulo'] == 'Plano X'
    assert 'pipeline_slug' not in cfg  # pinado (LLM não escolhe pipeline)


def test_loop_com_tools_executa_e_retorna_texto_final():
    integ = SimpleNamespace(tipo='openai', configuracoes_extras={}, api_key='k',
                            access_token='', client_secret='', base_url='')
    schema = ia_tools.schema_openai(['registrar_feedback'])
    chamadas = []

    def despacho(nome, args):
        chamadas.append((nome, args))
        return 'feedback ok'

    r1 = mock.Mock(status_code=200)
    r1.json.return_value = {'choices': [{'finish_reason': 'tool_calls', 'message': {
        'role': 'assistant',
        'tool_calls': [{'id': 't1', 'function': {
            'name': 'registrar_feedback', 'arguments': json.dumps({'nota': 8})}}]}}]}
    r2 = mock.Mock(status_code=200)
    r2.json.return_value = {'choices': [{'finish_reason': 'stop',
                                         'message': {'role': 'assistant', 'content': 'Obrigado!'}}]}
    with mock.patch('apps.automacao.services.ia.requests.post', side_effect=[r1, r2]) as mp:
        out = chamar_llm_com_tools(integ, [{'role': 'user', 'content': 'nota 8'}], schema, despacho)
    assert out == 'Obrigado!'
    assert chamadas == [('registrar_feedback', {'nota': 8})]
    assert mp.call_count == 2


def test_loop_sem_tools_cai_em_chamar_llm():
    integ = SimpleNamespace(tipo='openai', configuracoes_extras={})
    with mock.patch('apps.automacao.services.ia.chamar_llm', return_value='simples') as mc:
        out = chamar_llm_com_tools(integ, [{'role': 'user', 'content': 'oi'}], [], lambda n, a: '')
    assert out == 'simples'
    mc.assert_called_once()


@pytest.mark.parametrize('chave,arg,acao', [
    ('marcar_cliente', {'e_cliente': True}, 'marcar_cliente'),
    ('marcar_intencao', {'tem_intencao': True}, 'marcar_intencao'),
    ('marcar_intencao_energia', {'tem_interesse': True}, 'marcar_intencao_energia'),
])
def test_marcar_fatos_gravam_logsistema_tenant_safe(chave, arg, acao):
    ctx = SimpleNamespace(tenant=SimpleNamespace(pk=7), lead=SimpleNamespace(pk=42))
    with mock.patch('apps.sistema.models.LogSistema') as MLog:
        out = ia_tools.despachar(chave, arg, ctx)
    MLog.objects.create.assert_called_once()
    kw = MLog.objects.create.call_args.kwargs
    assert kw['tenant'] is ctx.tenant
    assert kw['acao'] == acao
    assert kw['entidade_id'] == 42
    assert kw['dados_extras']['valor'] is True
    assert 'registrado' in out


def test_no_ia_agente_usa_tools_quando_agente_tem():
    ag = SimpleNamespace(pk=5, nome='X', system_prompt='p', modelo='',
                         integracao_ia=SimpleNamespace(tipo='openai'), tools=['registrar_feedback'])
    ctx = Contexto(tenant=SimpleNamespace(pk=1), variaveis={'conteudo': 'oi'})
    with mock.patch('apps.automacao.models.Agente') as MA, \
         mock.patch('apps.automacao.services.ia.chamar_llm_com_tools', return_value='resp-tools') as mct:
        MA.all_tenants.filter.return_value.select_related.return_value.first.return_value = ag
        res = tipo_por_slug('ia_agente').executar({'agente_id': '5'}, {}, ctx)
    assert res.branch == 'sucesso'
    assert res.output['resposta'] == 'resp-tools'
    mct.assert_called_once()
