"""Tradutor: RegraPipelineEstagio (motor antigo do funil) → grafo de Fluxo (engine nova).

Migração da automação do funil (Fase 2, Passo 1). Converte cada regra num Fluxo
equivalente que dispara no pulso `crm_reavaliar_oportunidade` (Opção A, espelho fiel):

    [evento crm_reavaliar_oportunidade]
        → [condicao_comercial × N]   (AND: cada 'true' encadeia na próxima)
        → alvo:
            • regra COM estágio destino  → [mover_estagio]
            • regra de ação (sem estágio) → [acao_comercial × N] (roda todas, sucesso OU erro)

Paridade por construção: `condicao_comercial` e `acao_comercial` reusam os MESMOS
registries do motor antigo (`automacao_condicoes` e `_EXECUTORES_ACAO`), então a
avaliação/execução é o mesmíssimo código. O que o shadow (Passo 2) valida é a
ORQUESTRAÇÃO (quando dispara, quais nós, em que ordem), não o código das ações.

Puro (sem DB): opera sobre os objetos já carregados. `regra.estagio` pode ser None
(regra de ação). Semânticas cross-regra do motor antigo (primeiro-match-vence entre
regras de estágio; ordem por prioridade) NÃO são reproduzidas aqui — cada regra vira
um Fluxo independente. O comparador do shadow mede essas divergências antes do cutover.
"""

EVENTO_PULSO = 'crm_reavaliar_oportunidade'  # fallback: regra sem evento inferível

_DX = 240  # espaçamento horizontal dos nós (layout do editor)

# Config-driven (nada hardcoded por regra): o evento-gatilho de uma regra sai do
# TIPO da condição primária dela. As condições continuam como guarda no fluxo — o
# evento só define QUANDO reavaliar; a condição confirma o estado.
_EVENTO_POR_TIPO = {
    'tag': 'tag_adicionada',
    'historico_status': 'historico_contato',
    'servico_status': 'servico_hubsoft_mudou',
    'viabilidade_status': 'viabilidade_consultada',
    'conversa_modo': 'conversa_modo_mudou',
    'conversa_atribuida': 'conversa_atribuida',
    'lead_status_api': 'lead_status_mudou',
    'lead_campo': 'lead_campo_mudou',
    'oportunidade_dados_custom': 'conversa_modo_mudou',  # bot concluir ~ modo mudou
}

# Prioridade quando a regra tem várias condições-gatilho: a mais específica vence.
_PRIORIDADE = [
    'tag_adicionada', 'historico_contato', 'docs_validados', 'documento_status_mudou',
    'servico_hubsoft_mudou', 'viabilidade_consultada', 'conversa_atribuida',
    'conversa_modo_mudou', 'lead_status_mudou', 'lead_campo_mudou', 'oportunidade_criada',
]


def _evento_da_condicao(cond):
    """Evento de negócio que a condição representa (None se for só guarda, ex: score)."""
    tipo = (cond.get('tipo') or '').strip()
    op = (cond.get('operador') or '').strip()
    if tipo == 'imagem_status':
        # 'todas_iguais documentos_validos' = docs_validados; senão = mudança de status
        return 'docs_validados' if op == 'todas_iguais' else 'documento_status_mudou'
    if tipo == 'lead_campo':
        # campo AUSENTE ('nao_existe') = gatilho de entrada (op criada sem o dado);
        # campo GANHANDO valor = lead_campo_mudou.
        return 'oportunidade_criada' if op == 'nao_existe' else 'lead_campo_mudou'
    return _EVENTO_POR_TIPO.get(tipo)


def evento_gatilho_da_regra(regra):
    """Evento real que dispara a regra, inferido da condição primária. `None` = nenhuma
    condição-gatilho (o chamador cai pro EVENTO_PULSO)."""
    candidatos = {_evento_da_condicao(c) for c in (regra.condicoes or [])}
    candidatos.discard(None)
    if not candidatos:
        return None
    for ev in _PRIORIDADE:
        if ev in candidatos:
            return ev
    return next(iter(candidatos))


def _cond_node(cond, x):
    return {
        'tipo': 'condicao_comercial',
        'config': {
            'tipo_condicao': (cond.get('tipo') or '').strip(),
            'operador': (cond.get('operador') or 'igual').strip(),
            'valor': '' if cond.get('valor') is None else cond.get('valor'),
            'campo': (cond.get('campo') or '').strip(),
        },
        'pos': {'x': x, 'y': 0},
        'label': (cond.get('tipo') or 'condição'),
    }


def _acao_node(acao, x):
    return {
        'tipo': 'acao_comercial',
        'config': {
            'tipo_acao': (acao.get('tipo') or '').strip(),
            'config': acao.get('config') or {},
        },
        'pos': {'x': x, 'y': 0},
        'label': (acao.get('tipo') or 'ação'),
    }


def regra_para_grafo(regra, evento=None):
    """Converte a regra no grafo `{inicio, nodes, conexoes}` do Fluxo. Puro.

    `evento` = gatilho do fluxo; se None, infere o evento real da regra (condição
    primária) e cai pro EVENTO_PULSO se não houver. As condições continuam como
    guarda — o evento define o QUANDO, a condição confirma o estado."""
    evento = evento or evento_gatilho_da_regra(regra) or EVENTO_PULSO
    nodes, conexoes = {}, []
    x = 0
    nodes['trigger'] = {
        'tipo': 'evento',
        'config': {'evento': evento, 'filtros': []},
        'pos': {'x': x, 'y': 0},
        'label': f'Gatilho: {evento}',
    }

    # Corrente de condições (AND): cada 'true' liga na próxima; 'false' termina o fluxo.
    anterior, saida = 'trigger', 'default'
    for i, cond in enumerate(regra.condicoes or []):
        x += _DX
        h = f'cond{i}'
        nodes[h] = _cond_node(cond, x)
        conexoes.append({'de': anterior, 'para': h, 'saida': saida})
        anterior, saida = h, 'true'

    estagio = getattr(regra, 'estagio', None)
    if estagio is not None:
        # Regra de estágio: só move (o motor antigo ignora `acoes` dessas regras).
        x += _DX
        nome = getattr(estagio, 'nome', '') or getattr(estagio, 'slug', '') or '?'
        nodes['mover'] = {
            'tipo': 'mover_estagio',
            'config': {'estagio_slug': getattr(estagio, 'slug', '') or ''},
            'pos': {'x': x, 'y': 0},
            'label': f'Mover → {nome}',
        }
        conexoes.append({'de': anterior, 'para': 'mover', 'saida': saida})
    else:
        # Regra de ação: roda todas as ações em sequência, independente de sucesso/erro
        # (fiel ao motor antigo, que executa cada ação num try/except próprio).
        prev, prev_saidas = anterior, [saida]
        for i, acao in enumerate(regra.acoes or []):
            x += _DX
            h = f'acao{i}'
            nodes[h] = _acao_node(acao, x)
            for s in prev_saidas:
                conexoes.append({'de': prev, 'para': h, 'saida': s})
            prev, prev_saidas = h, ['sucesso', 'erro']

    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


def descricao_da_regra(regra):
    """Texto curto pro Fluxo, deixando claro que é auto-gerado da regra."""
    tipo = 'estágio' if getattr(regra, 'estagio', None) is not None else 'ação'
    n_cond = len(getattr(regra, 'condicoes', None) or [])
    return (f'Fluxo gerado automaticamente da RegraPipelineEstagio #{getattr(regra, "pk", "?")} '
            f'(regra de {tipo}, {n_cond} condição(ões)). Migração da automação do funil. '
            f'NÃO editar à mão: rode migrar_regras_pipeline pra ressincronizar.')


def regra_traduzivel(regra):
    """(traduzível?, motivo). O motor antigo nunca dispara regra sem condição
    (`_regra_bate` exige ≥1) nem regra de ação sem ações — traduzi-las criaria um
    fluxo que dispara à toa. Essas são puladas (mortas no motor antigo)."""
    if not (getattr(regra, 'condicoes', None) or []):
        return False, 'sem condições (nunca dispara no motor antigo)'
    if getattr(regra, 'estagio', None) is None and not (getattr(regra, 'acoes', None) or []):
        return False, 'regra de ação sem ações'
    return True, ''
