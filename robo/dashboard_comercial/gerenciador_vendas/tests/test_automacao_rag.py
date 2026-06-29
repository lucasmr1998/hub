"""
Testes do RAG do agente (D4): `buscar_conhecimento` (formatação, vazio, erro) e a
tool `consultar_base_conhecimento` (passa as categorias do agente, tenant-safe).

Sem DB nem pgvector: `buscar_artigos` e `buscar_conhecimento` são mockados.
"""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.services import ia_tools, rag


def test_rag_tool_registrada():
    assert any(t['chave'] == 'consultar_base_conhecimento' for t in ia_tools.tools_disponiveis())


def test_buscar_conhecimento_formata_resultados():
    arts = [
        {'artigo': SimpleNamespace(titulo='Planos', resumo='Temos 3 planos.', conteudo=''), 'distancia': 0.1},
        {'artigo': SimpleNamespace(titulo='Horário', resumo='', conteudo='9h às 18h'), 'distancia': 0.2},
    ]
    with mock.patch('apps.suporte.services.buscar_artigos', return_value=arts):
        out = rag.buscar_conhecimento(SimpleNamespace(pk=1), 'planos?')
    assert '## Planos' in out and 'Temos 3 planos.' in out
    assert '## Horário' in out and '9h às 18h' in out


def test_buscar_conhecimento_vazio_registra_gap():
    with mock.patch('apps.suporte.services.buscar_artigos', return_value=[]), \
         mock.patch('apps.suporte.services.registrar_pergunta_sem_resposta') as mreg:
        out = rag.buscar_conhecimento(SimpleNamespace(pk=1), 'qual o prazo do desconto?')
    assert 'Nada encontrado' in out
    mreg.assert_called_once()
    assert mreg.call_args.kwargs['pergunta'] == 'qual o prazo do desconto?'


def test_buscar_conhecimento_erro_degrada_e_nao_registra_gap():
    with mock.patch('apps.suporte.services.buscar_artigos', side_effect=RuntimeError('pgvector off')), \
         mock.patch('apps.suporte.services.registrar_pergunta_sem_resposta') as mreg:
        out = rag.buscar_conhecimento(SimpleNamespace(pk=1), 'qual o prazo?')
    assert 'Não foi possível' in out
    mreg.assert_not_called()  # erro de infra não vira "pergunta sem resposta"


def test_tool_consultar_base_passa_categorias_do_agente():
    ctx = SimpleNamespace(tenant=SimpleNamespace(pk=3))
    agente = SimpleNamespace(base_categorias=['5', '7'])
    with mock.patch('apps.automacao.services.rag.buscar_conhecimento', return_value='resultado') as mb:
        out = ia_tools.despachar('consultar_base_conhecimento', {'pergunta': 'planos?'}, ctx, agente)
    assert out == 'resultado'
    assert mb.call_args.kwargs['categorias'] == ['5', '7']
    assert mb.call_args[0][0] is ctx.tenant


def test_tool_consultar_base_sem_agente_usa_base_inteira():
    ctx = SimpleNamespace(tenant=SimpleNamespace(pk=3))
    with mock.patch('apps.automacao.services.rag.buscar_conhecimento', return_value='r') as mb:
        ia_tools.despachar('consultar_base_conhecimento', {'pergunta': 'x'}, ctx, None)
    assert mb.call_args.kwargs['categorias'] == []
