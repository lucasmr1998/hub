"""
Testes do nó Agente IA (ia_agente).

Sem DB nem rede: o lookup do `Agente` e o `chamar_llm` são mockados.
"""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**kwargs):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='alpha'), **kwargs)


def _fake_agente(**over):
    base = dict(pk=5, nome='NPS', system_prompt='Você é um atendente.', modelo='',
                integracao_ia=SimpleNamespace(tipo='openai'))
    base.update(over)
    return SimpleNamespace(**base)


def _patch_agente(fake):
    """Patcheia Agente.all_tenants.filter(...).select_related(...).first() → fake."""
    p = mock.patch('apps.automacao.models.Agente')
    MA = p.start()
    MA.all_tenants.filter.return_value.select_related.return_value.first.return_value = fake
    return p


def test_registrado():
    assert tipo_por_slug('ia_agente') is not None


def test_validar_config():
    no = tipo_por_slug('ia_agente')
    assert no.validar_config({}) != []
    assert no.validar_config({'agente_id': '5'}) == []


@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm', return_value='Olá! Como posso ajudar?')
def test_caminho_feliz_responde(mock_llm):
    p = _patch_agente(_fake_agente())
    try:
        res = tipo_por_slug('ia_agente').executar(
            {'agente_id': '5'}, {}, _ctx(variaveis={'conteudo': 'oi'}))
    finally:
        p.stop()
    assert res.branch == 'sucesso'
    assert res.output['resposta'] == 'Olá! Como posso ajudar?'
    # memória = a conversa: sem write-back de histórico (não promove _hist).
    messages = mock_llm.call_args[0][1]
    assert messages[0]['role'] == 'system'
    assert messages[-1] == {'role': 'user', 'content': 'oi'}


@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm', return_value='resp2')
def test_usa_var_resposta_na_retoma_com_memoria(mock_llm):
    p = _patch_agente(_fake_agente())
    try:
        ctx = _ctx(variaveis={
            'resposta': 'quero saber o preço',
            # memória da conversa (no teste, os turnos vêm em _memoria_turnos)
            '_memoria_turnos': [{'role': 'user', 'content': 'oi'},
                                {'role': 'assistant', 'content': 'olá'}],
        })
        res = tipo_por_slug('ia_agente').executar({'agente_id': '5'}, {}, ctx)
    finally:
        p.stop()
    assert res.branch == 'sucesso'
    messages = mock_llm.call_args[0][1]
    assert messages[-1] == {'role': 'user', 'content': 'quero saber o preço'}
    assert {'role': 'assistant', 'content': 'olá'} in messages


@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm', return_value=None)
def test_llm_falha_vira_erro(mock_llm):
    p = _patch_agente(_fake_agente())
    try:
        res = tipo_por_slug('ia_agente').executar({'agente_id': '5'}, {}, _ctx(variaveis={'conteudo': 'oi'}))
    finally:
        p.stop()
    assert res.branch == 'erro'


def test_agente_inexistente_vira_erro():
    p = _patch_agente(None)
    try:
        res = tipo_por_slug('ia_agente').executar({'agente_id': '999'}, {}, _ctx(variaveis={'conteudo': 'oi'}))
    finally:
        p.stop()
    assert res.branch == 'erro'


@mock.patch('apps.automacao.nodes.ia_agente.chamar_llm')
def test_mensagem_vazia_nao_chama_llm(mock_llm):
    p = _patch_agente(_fake_agente())
    try:
        res = tipo_por_slug('ia_agente').executar({'agente_id': '5'}, {}, _ctx())
    finally:
        p.stop()
    assert res.branch == 'erro'
    mock_llm.assert_not_called()
