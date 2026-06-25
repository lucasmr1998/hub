"""
Tradutor: regra do motor antigo de marketing (`RegraAutomacao`) → `Fluxo` da engine nova.

Converte os dois formatos legacy:
- **visual** (`modo_fluxo=True`): `NodoFluxo` + `ConexaoNodo` (já é grafo).
- **linear** (`modo_fluxo=False`): `CondicaoRegra` (AND) + `AcaoRegra` (sequência + delay).

Produz o `grafo` ({inicio, nodes, conexoes}) que o runtime novo consome. NÃO salva —
`traduzir_regra` devolve `(grafo, avisos)`; o command decide dry-run vs criar `Fluxo`.

Cuidados:
- Template **flat** legacy (`{{lead_nome}}`) vira **`{{var.lead_nome}}`** (a engine nova
  põe escalares do evento em `var.*`); dot-notation existente é mantida.
- Ações sem nó equivalente (email, whatsapp-N8N, webhook, hubsoft) viram **aviso** e o
  fluxo fica incompleto de propósito (essas regras seguem no motor antigo até terem nó).
- Freio: `max_execucoes_por_lead`/`cooldown_horas` da regra entram no nó-gatilho.
"""
import re

# Ações que a engine nova já tem como nó (1:1 pelo subtipo).
_ACAO_SUPORTADA = {
    'criar_tarefa', 'notificacao_sistema', 'criar_oportunidade', 'criar_venda',
    'mover_estagio', 'atribuir_responsavel', 'dar_pontos',
}
# Ações sem nó na engine nova (ficam no motor antigo).
_ACAO_SEM_NO = {'enviar_email', 'enviar_whatsapp', 'webhook', 'sincronizar_prospecto_hubsoft'}

# Renome de campo de config: legacy → novo, por subtipo de ação.
_RENAME = {
    'criar_tarefa': {'tipo_tarefa': 'tipo'},
}

_TOKEN = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')

# O `tipo` do NodoFluxo aparece em PT e EN nos dados (versões diferentes do editor).
# Normaliza tudo pra EN antes de mapear.
_TIPO_NORM = {'acao': 'action', 'ação': 'action', 'condicao': 'condition', 'condição': 'condition'}


def _conv_template(valor):
    """`{{lead_nome}}` (flat legacy) → `{{var.lead_nome}}`. Mantém dot-notation (lead.nome)."""
    if not isinstance(valor, str):
        return valor

    def _sub(m):
        chave = m.group(1).strip()
        if '.' in chave:            # já é dot-notation (lead.nome, var.x, nodes.x)
            return m.group(0)
        return '{{var.' + chave + '}}'

    return _TOKEN.sub(_sub, valor)


def _conv_config(subtipo, cfg):
    ren = _RENAME.get(subtipo, {})
    return {ren.get(k, k): _conv_template(v) for k, v in (cfg or {}).items()}


def _map_saida(origem_tipo, tipo_saida):
    """Saída legacy (default/true/false) → saída do nó novo, pelo tipo da origem."""
    if tipo_saida in ('true', 'false'):
        return tipo_saida
    if origem_tipo in ('evento', 'delay'):
        return 'default'
    if origem_tipo in _ACAO_SUPORTADA:
        return 'sucesso'
    return 'default'


def traduzir_regra(regra):
    """Converte uma `RegraAutomacao` → (grafo, avisos). Não salva."""
    return _traduzir_visual(regra) if regra.modo_fluxo else _traduzir_linear(regra)


def _no_gatilho(regra, evento, pos=None):
    return {'tipo': 'evento', 'config': {
        'evento': evento,
        'filtros': [],
        'max_por_lead': regra.max_execucoes_por_lead or 0,
        'cooldown_horas': regra.cooldown_horas or 0,
    }, 'pos': pos or {'x': 60, 'y': 80}, 'nome': 'Evento'}


def _no_da_acao(subtipo, cfg, pos, avisos):
    """Devolve o dict do nó da ação, ou None (com aviso) se não suportada."""
    if subtipo in _ACAO_SEM_NO:
        avisos.append(f'ação sem nó na engine nova: "{subtipo}" (regra segue no motor antigo)')
        return None
    if subtipo not in _ACAO_SUPORTADA:
        avisos.append(f'ação desconhecida: "{subtipo}"')
        return None
    return {'tipo': subtipo, 'config': _conv_config(subtipo, cfg), 'pos': pos, 'nome': subtipo}


def _traduzir_visual(regra):
    from apps.marketing.automacoes.models import NodoFluxo, ConexaoNodo
    avisos, nodes, tipo_por_nodo = [], {}, {}
    inicio = None

    def h(nid):
        return f'n{nid}'

    for n in NodoFluxo.all_tenants.filter(regra=regra).order_by('id'):
        cfg = n.configuracao or {}
        pos = {'x': n.pos_x or 0, 'y': n.pos_y or 0}
        tipo = _TIPO_NORM.get(n.tipo, n.tipo)
        if tipo == 'trigger':
            nodes[h(n.id)] = _no_gatilho(regra, cfg.get('evento') or n.subtipo or regra.evento, pos)
            tipo_por_nodo[n.id] = 'evento'
            inicio = h(n.id)
        elif tipo == 'condition':
            nodes[h(n.id)] = {'tipo': 'if', 'config': {
                'esquerda': _conv_template('{{' + (cfg.get('campo') or '') + '}}'),
                'operador': cfg.get('operador') or 'igual',
                'direita': _conv_template(str(cfg.get('valor') or '')),
            }, 'pos': pos, 'nome': 'Condição'}
            tipo_por_nodo[n.id] = 'if'
        elif tipo == 'delay':
            nodes[h(n.id)] = {'tipo': 'delay', 'config': {
                'valor': cfg.get('valor') or cfg.get('delay_valor') or 0,
                'unidade': cfg.get('unidade') or cfg.get('delay_unidade') or 'minutos',
            }, 'pos': pos, 'nome': 'Aguardar'}
            tipo_por_nodo[n.id] = 'delay'
        elif tipo == 'action':
            no = _no_da_acao(n.subtipo, cfg, pos, avisos)
            if no is not None:
                nodes[h(n.id)] = no
                tipo_por_nodo[n.id] = n.subtipo

    conexoes = []
    for c in ConexaoNodo.all_tenants.filter(nodo_origem__regra=regra):
        if c.nodo_origem_id not in tipo_por_nodo or c.nodo_destino_id not in tipo_por_nodo:
            continue  # nó pulado (ação não suportada) — conexão cai junto
        conexoes.append({
            'de': h(c.nodo_origem_id), 'para': h(c.nodo_destino_id),
            'saida': _map_saida(tipo_por_nodo[c.nodo_origem_id], c.tipo_saida),
        })

    return {'inicio': inicio, 'nodes': nodes, 'conexoes': conexoes}, avisos


def _parse_config_linear(texto):
    """Config legacy de AcaoRegra é texto livre (`chave: valor` por linha). Best-effort."""
    out = {}
    for linha in (texto or '').splitlines():
        if ':' in linha:
            k, _, v = linha.partition(':')
            k = k.strip().lower()
            if k:
                out[k] = v.strip()
    return out


def _traduzir_linear(regra):
    from apps.marketing.automacoes.models import CondicaoRegra, AcaoRegra
    avisos, nodes, conexoes = [], {}, []
    nodes['gatilho'] = _no_gatilho(regra, regra.evento)
    anterior, saida_anterior = 'gatilho', 'default'
    y = 80

    # Condições (AND) → ifs encadeados; só a saída 'true' continua.
    for i, cond in enumerate(CondicaoRegra.all_tenants.filter(regra=regra)):
        y += 120
        h = f'cond{i}'
        nodes[h] = {'tipo': 'if', 'config': {
            'esquerda': _conv_template('{{' + (cond.campo or '') + '}}'),
            'operador': cond.operador or 'igual',
            'direita': _conv_template(str(cond.valor or '')),
        }, 'pos': {'x': 60, 'y': y}, 'nome': 'Condição'}
        conexoes.append({'de': anterior, 'para': h, 'saida': saida_anterior})
        anterior, saida_anterior = h, 'true'

    # Ações em sequência (+ delay).
    for j, acao in enumerate(AcaoRegra.all_tenants.filter(regra=regra).order_by('ordem')):
        y += 120
        if acao.delay_ativo:
            hd = f'delay{j}'
            nodes[hd] = {'tipo': 'delay', 'config': {
                'valor': acao.delay_valor or 0, 'unidade': acao.delay_unidade or 'minutos',
            }, 'pos': {'x': 60, 'y': y}, 'nome': 'Aguardar'}
            conexoes.append({'de': anterior, 'para': hd, 'saida': saida_anterior})
            anterior, saida_anterior = hd, 'default'
            y += 120
        no = _no_da_acao(acao.tipo, _parse_config_linear(acao.configuracao), {'x': 60, 'y': y}, avisos)
        if no is None:
            continue
        h = f'acao{j}'
        nodes[h] = no
        conexoes.append({'de': anterior, 'para': h, 'saida': saida_anterior})
        anterior, saida_anterior = h, 'sucesso'

    return {'inicio': 'gatilho', 'nodes': nodes, 'conexoes': conexoes}, avisos
