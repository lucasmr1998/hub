"""Comparador de paridade da migração do funil — Fase 2, Passo 3.

Cruza, por pulso, o que o motor ANTIGO realmente fez vs o que o shadow (motor NOVO)
FARIA, pra provar paridade antes do cutover.

Fontes (LogSistema, todos com entidade_id = op):
- `motor_disparado`  → marca um PULSO (o motor antigo reavaliou a op).
- `mover_regra`      → o antigo MOVEU por uma regra (dados_extras.regra_id).
- `acoes_regra`      → o antigo executou AÇÕES de uma regra (dados_extras.regra_id).
- `shadow_fluxo`     → o novo DISPARARIA fluxos (dados_extras.would_fire[].origem_regra).

Correlação: por op, cada pulso captura os fires/shadow entre ele e o próximo pulso.
Compara o conjunto de regras: `divergencia = (antigo XOR novo)`. `origem_regra` do
fluxo == `regra_id` da regra que o originou, então os conjuntos são comparáveis direto.

Núcleo (`comparar_op`) é puro (sem DB) — recebe eventos normalizados. O command
`comparar_shadow_pipeline` puxa do LogSistema e agrega.
"""

_ACAO_PULSO = 'motor_disparado'
_ACAO_FIRE = ('mover_regra', 'acoes_regra')
_ACAO_SHADOW = 'shadow_fluxo'


def comparar_op(eventos):
    """`eventos`: lista de dicts `{acao, ts, rules:set}` de UMA op, ordenada por ts.
    Devolve a lista de pulsos: `{antigo:set, novo:set, match, so_antigo:set, so_novo:set}`.
    Eventos antes do 1º pulso são ignorados (sem pulso pra ancorar)."""
    pulsos = []
    atual = None
    for ev in eventos:
        acao = ev.get('acao')
        if acao == _ACAO_PULSO:
            if atual is not None:
                pulsos.append(_fechar(atual))
            atual = {'antigo': set(), 'novo': set()}
        elif atual is None:
            continue  # fire/shadow sem pulso ancorando → ignora
        elif acao in _ACAO_FIRE:
            atual['antigo'] |= ev.get('rules') or set()
        elif acao == _ACAO_SHADOW:
            atual['novo'] |= ev.get('rules') or set()
    if atual is not None:
        pulsos.append(_fechar(atual))
    return pulsos


def comparar_op_agregado(eventos):
    """v2 (eventos finos): agrega TODOS os eventos da op na janela, SEM fronteira de
    pulso — os eventos finos do shadow disparam em momentos diferentes do
    `motor_disparado`, então compara-se o CONJUNTO de regras ao longo do tempo:
    o que o antigo disparou (mover_regra/acoes_regra) vs o que o shadow faria
    (shadow_fluxo). Devolve 0 ou 1 pulso (a op inteira como um bloco)."""
    antigo, novo = set(), set()
    for ev in eventos:
        acao = ev.get('acao')
        if acao in _ACAO_FIRE:
            antigo |= ev.get('rules') or set()
        elif acao == _ACAO_SHADOW:
            novo |= ev.get('rules') or set()
    return [_fechar({'antigo': antigo, 'novo': novo})] if (antigo or novo) else []


def _fechar(p):
    antigo, novo = p['antigo'], p['novo']
    return {
        'antigo': antigo, 'novo': novo,
        'so_antigo': antigo - novo,   # o antigo fez, o novo NÃO faria (miss do novo)
        'so_novo': novo - antigo,     # o novo faria, o antigo NÃO fez (extra do novo)
        'match': antigo == novo,
    }


def resumir(pulsos):
    """Agrega uma lista de pulsos (de comparar_op) num resumo."""
    total = len(pulsos)
    com_atividade = [p for p in pulsos if p['antigo'] or p['novo']]
    divergentes = [p for p in pulsos if not p['match']]
    so_antigo, so_novo = set(), set()
    for p in divergentes:
        so_antigo |= p['so_antigo']
        so_novo |= p['so_novo']
    return {
        'pulsos': total,
        'pulsos_com_atividade': len(com_atividade),
        'divergentes': len(divergentes),
        'paridade': (total - len(divergentes)) / total if total else 1.0,
        'regras_so_antigo': sorted(so_antigo),   # regras que o novo perderia
        'regras_so_novo': sorted(so_novo),       # regras que o novo faria a mais
    }
