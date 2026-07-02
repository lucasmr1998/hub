"""Testes do runner shadow (log-only) da migração do funil — puro, sem DB."""
from types import SimpleNamespace

from apps.automacao.tradutor_pipeline import regra_para_grafo
from apps.automacao.shadow import avaliar_fluxo_shadow, avaliar_pulso_shadow


def _regra(condicoes=None, acoes=None, estagio=None, pk=1):
    return SimpleNamespace(pk=pk, nome='R', condicoes=condicoes or [], acoes=acoes or [],
                           estagio=estagio, estagio_id=getattr(estagio, 'pk', None))


def test_estagio_dispara_quando_condicoes_passam():
    est = SimpleNamespace(pk=9, slug='perdido', nome='Perdido')
    g = regra_para_grafo(_regra(condicoes=[{'tipo': 'viabilidade', 'operador': 'igual', 'valor': 'neg'}],
                                estagio=est))
    disparou, acoes = avaliar_fluxo_shadow(g, lambda cfg: True)
    assert disparou is True
    assert len(acoes) == 1 and acoes[0]['no'] == 'mover_estagio'


def test_nao_dispara_quando_condicao_falha():
    est = SimpleNamespace(pk=9, slug='perdido', nome='Perdido')
    g = regra_para_grafo(_regra(condicoes=[{'tipo': 'x', 'operador': 'igual', 'valor': 'y'}], estagio=est))
    disparou, acoes = avaliar_fluxo_shadow(g, lambda cfg: False)
    assert disparou is False and acoes == []


def test_acoes_registradas_todas_em_ordem():
    g = regra_para_grafo(_regra(
        condicoes=[{'tipo': 'a', 'operador': 'existe'}],
        acoes=[{'tipo': 'criar_venda'},
               {'tipo': 'enviar_venda_whatsapp', 'config': {'telefone_destino': '55'}}]))
    disparou, acoes = avaliar_fluxo_shadow(g, lambda cfg: True)
    assert disparou is True
    assert [a['tipo'] for a in acoes] == ['criar_venda', 'enviar_venda_whatsapp']
    # config da ação é preservado
    assert acoes[1]['config'] == {'telefone_destino': '55'}


def test_and_precisa_de_todas_as_condicoes():
    g = regra_para_grafo(_regra(
        condicoes=[{'tipo': 'a', 'operador': 'existe'}, {'tipo': 'b', 'operador': 'igual', 'valor': '1'}],
        acoes=[{'tipo': 'criar_venda'}]))
    # passa a 1ª (tipo a), falha a 2ª (tipo b) → não dispara
    disparou, acoes = avaliar_fluxo_shadow(g, lambda cfg: cfg.get('tipo_condicao') == 'a')
    assert disparou is False and acoes == []


def test_grafo_vazio_nao_quebra():
    disparou, acoes = avaliar_fluxo_shadow({}, lambda cfg: True)
    assert disparou is False and acoes == []


def test_avaliar_pulso_shadow_sem_oportunidade_nao_quebra():
    # guardas: None e sem tenant não estouram
    avaliar_pulso_shadow(None)
    avaliar_pulso_shadow(SimpleNamespace(tenant=None))
