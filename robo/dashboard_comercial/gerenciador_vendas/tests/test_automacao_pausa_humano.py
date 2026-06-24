"""
Testes da pausa-por-humano (D5): o evento carrega `var.modo_atendimento`, a retoma
o refresca, e o fluxo decide via nó `if` (declarativo, não quebra o loop por default).
"""
from types import SimpleNamespace

from apps.automacao.nodes import Contexto, tipo_por_slug


def _ctx(**vars):
    return Contexto(tenant=SimpleNamespace(pk=1), variaveis=vars)


def test_evento_mensagem_recebida_expoe_modo_atendimento():
    from apps.automacao.eventos import EVENTOS
    nomes = [s['nome'] for s in EVENTOS['mensagem_recebida']['subcampos']]
    assert 'var.modo_atendimento' in nomes


def test_if_pausa_quando_humano_assumiu():
    no = tipo_por_slug('if')
    cfg = {'esquerda': '{{var.modo_atendimento}}', 'operador': 'igual', 'direita': 'humano'}
    # humano → branch 'true' (o fluxo encerra nessa saída, bot não responde)
    assert no.executar(cfg, {}, _ctx(modo_atendimento='humano')).branch == 'true'
    # bot → branch 'false' (segue pro Agente IA)
    assert no.executar(cfg, {}, _ctx(modo_atendimento='bot')).branch == 'false'


def test_retomar_por_resposta_aceita_modo_atendimento():
    # Valida a nova assinatura sem tocar o DB: sem tenant/chave → False, sem erro.
    from apps.automacao.execucao import retomar_por_resposta
    assert retomar_por_resposta(None, '', '', 'humano') is False
    assert retomar_por_resposta(None, 'x', 'oi') is False  # 4º arg opcional (compat)
