"""Testes do tradutor RegraPipelineEstagio → grafo de Fluxo (puro, sem DB)."""
from types import SimpleNamespace

from apps.automacao.tradutor_pipeline import (
    regra_para_grafo, regra_traduzivel, EVENTO_PULSO,
)
from apps.automacao.runtime import validar_fluxo


def _regra(condicoes=None, acoes=None, estagio=None, pk=1):
    return SimpleNamespace(pk=pk, nome='R', condicoes=condicoes or [],
                           acoes=acoes or [], estagio=estagio,
                           estagio_id=getattr(estagio, 'pk', None))


def test_trigger_e_o_pulso():
    g = regra_para_grafo(_regra(condicoes=[{'tipo': 'tag', 'operador': 'igual', 'valor': 'x'}]))
    assert g['inicio'] == 'trigger'
    assert g['nodes']['trigger']['tipo'] == 'evento'
    assert g['nodes']['trigger']['config']['evento'] == EVENTO_PULSO


def test_regra_de_estagio_gera_mover_e_valida():
    estagio = SimpleNamespace(pk=9, slug='perdido', nome='Perdido')
    regra = _regra(
        condicoes=[{'tipo': 'viabilidade', 'operador': 'igual', 'valor': 'negativa', 'campo': ''}],
        estagio=estagio)
    g = regra_para_grafo(regra)
    assert g['nodes']['cond0']['tipo'] == 'condicao_comercial'
    assert g['nodes']['cond0']['config']['tipo_condicao'] == 'viabilidade'
    assert g['nodes']['mover']['tipo'] == 'mover_estagio'
    assert g['nodes']['mover']['config']['estagio_slug'] == 'perdido'
    # aresta trigger→cond0 (default) e cond0→mover (true)
    assert {'de': 'trigger', 'para': 'cond0', 'saida': 'default'} in g['conexoes']
    assert {'de': 'cond0', 'para': 'mover', 'saida': 'true'} in g['conexoes']
    assert validar_fluxo(g) == []


def test_condicoes_encadeiam_em_and():
    regra = _regra(condicoes=[
        {'tipo': 'a', 'operador': 'existe'},
        {'tipo': 'b', 'operador': 'igual', 'valor': '1'},
        {'tipo': 'c', 'operador': 'diferente', 'valor': '2'},
    ], acoes=[{'tipo': 'criar_venda'}])
    g = regra_para_grafo(regra)
    assert {'de': 'cond0', 'para': 'cond1', 'saida': 'true'} in g['conexoes']
    assert {'de': 'cond1', 'para': 'cond2', 'saida': 'true'} in g['conexoes']
    assert validar_fluxo(g) == []


def test_regra_de_acao_encadeia_acoes_e_valida():
    regra = _regra(
        condicoes=[{'tipo': 'converteu_venda', 'operador': 'igual', 'valor': 'true'}],
        acoes=[{'tipo': 'criar_venda'},
               {'tipo': 'enviar_venda_whatsapp', 'config': {'telefone_destino': '5511999'}}])
    g = regra_para_grafo(regra)
    assert g['nodes']['acao0']['config']['tipo_acao'] == 'criar_venda'
    assert g['nodes']['acao1']['config']['tipo_acao'] == 'enviar_venda_whatsapp'
    assert g['nodes']['acao1']['config']['config'] == {'telefone_destino': '5511999'}
    # cond0 → acao0 (true); acao0 → acao1 por sucesso E erro (roda todas, fiel ao antigo)
    assert {'de': 'cond0', 'para': 'acao0', 'saida': 'true'} in g['conexoes']
    assert {'de': 'acao0', 'para': 'acao1', 'saida': 'sucesso'} in g['conexoes']
    assert {'de': 'acao0', 'para': 'acao1', 'saida': 'erro'} in g['conexoes']
    assert validar_fluxo(g) == []


def test_regra_traduzivel_pula_sem_condicao():
    ok, motivo = regra_traduzivel(_regra(condicoes=[], acoes=[{'tipo': 'criar_venda'}]))
    assert ok is False and 'condi' in motivo.lower()


def test_regra_traduzivel_pula_acao_sem_acoes():
    ok, motivo = regra_traduzivel(_regra(condicoes=[{'tipo': 'a', 'operador': 'existe'}], acoes=[]))
    assert ok is False


def test_regra_traduzivel_aceita_validas():
    estagio = SimpleNamespace(pk=9, slug='perdido', nome='Perdido')
    assert regra_traduzivel(_regra(condicoes=[{'tipo': 'a', 'operador': 'existe'}], estagio=estagio))[0]
    assert regra_traduzivel(_regra(condicoes=[{'tipo': 'a', 'operador': 'existe'}],
                                   acoes=[{'tipo': 'criar_venda'}]))[0]
