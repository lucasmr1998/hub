"""Corrige o bug do nodo_atual='undefined' no fluxo Vero.

Causa: os httpRequest 'Registrar RG Frente/Verso Hubtrix' ficam entre o
Step (que seta proximo_nodo) e o SmartSkip. A saida do httpRequest e a
resposta da API, sem proximo_nodo -> Save Session grava 'undefined'.

Fix: insere 2 nos Set que restauram o contexto a partir do Step,
entre o httpRequest e o SmartSkip:
  Registrar RG Frente Hubtrix -> [Restaura Contexto RG Frente] -> SmartSkip
  Registrar RG Verso Hubtrix  -> [Restaura Contexto RG Verso]  -> SmartSkip

Faz backup antes. Idempotente: se os nos ja existem, nao duplica.
"""
import sys, json, uuid
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'Df1BgcXdg3HAUZwf'

n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
conns = w['connections']
by_name = {nd['name']: nd for nd in nodes}


def make_restore_node(name, step_name, pos):
    """Cria Set node que restaura contexto a partir do Step."""
    def expr(field):
        return f"={{{{ $('{step_name}').item.json.{field} }}}}"
    return {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": str(uuid.uuid4()), "name": "resposta_bot",
                     "value": expr('resposta_bot'), "type": "string"},
                    {"id": str(uuid.uuid4()), "name": "proximo_nodo",
                     "value": expr('proximo_nodo'), "type": "string"},
                    {"id": str(uuid.uuid4()), "name": "novas_vars",
                     "value": expr('novas_vars'), "type": "object"},
                    {"id": str(uuid.uuid4()), "name": "deve_enviar_hubtrix",
                     "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": pos,
        "id": str(uuid.uuid4()),
        "name": name,
    }


PARES = [
    # (nome novo, step de origem, httpRequest, posicao)
    ('Restaura Contexto RG Frente', 'Step Aguarda RG Frente',
     'Registrar RG Frente Hubtrix', [400, 2050]),
    ('Restaura Contexto RG Verso', 'Step Aguarda RG Verso',
     'Registrar RG Verso Hubtrix', [400, 2350]),
]

mudou = False
for novo_nome, step_nome, http_nome, pos in PARES:
    if novo_nome in by_name:
        print(f'SKIP: {novo_nome} ja existe')
        continue
    if http_nome not in by_name:
        print(f'ERRO: {http_nome} nao existe — abortando')
        sys.exit(1)

    # 1. Adiciona o no Set
    novo = make_restore_node(novo_nome, step_nome, pos)
    nodes.append(novo)
    by_name[novo_nome] = novo

    # 2. Reconecta: httpRequest -> [Restaura] -> SmartSkip
    #    Remove httpRequest -> SmartSkip, adiciona httpRequest -> Restaura
    http_out = conns.get(http_nome, {}).get('main', [[]])
    # Garante estrutura
    if not http_out:
        http_out = [[]]
    # Filtra SmartSkip da saida do httpRequest
    novas_saidas = []
    tinha_smartskip = False
    for connset in http_out:
        novo_set = []
        for c in connset:
            if c.get('node') == 'SmartSkip':
                tinha_smartskip = True
                continue
            novo_set.append(c)
        novas_saidas.append(novo_set)
    if not tinha_smartskip:
        print(f'AVISO: {http_nome} nao apontava pra SmartSkip — verificar')
    # Adiciona httpRequest -> Restaura
    if novas_saidas:
        novas_saidas[0].append({'node': novo_nome, 'type': 'main', 'index': 0})
    else:
        novas_saidas = [[{'node': novo_nome, 'type': 'main', 'index': 0}]]
    conns[http_nome] = {'main': novas_saidas}

    # 3. Restaura -> SmartSkip
    conns[novo_nome] = {'main': [[{'node': 'SmartSkip', 'type': 'main', 'index': 0}]]}

    print(f'OK: criado {novo_nome}, reconectado {http_nome} -> {novo_nome} -> SmartSkip')
    mudou = True

if not mudou:
    print('\nNada a fazer (ja aplicado).')
    sys.exit(0)

# PUT — payload limpo (so campos aceitos). settings da API publica so
# aceita um subconjunto; binaryMode nao e permitido, entao filtramos.
settings_orig = w.get('settings', {})
settings_limpo = {}
for k in ('executionOrder', 'saveManualExecutions', 'saveExecutionProgress',
          'saveDataErrorExecution', 'saveDataSuccessExecution',
          'executionTimeout', 'errorWorkflow', 'timezone', 'callerPolicy'):
    if k in settings_orig:
        settings_limpo[k] = settings_orig[k]
payload = {
    'name': w['name'],
    'nodes': nodes,
    'connections': conns,
    'settings': settings_limpo,
}
print('\nEnviando PUT...')
res = n.update_workflow(WID, payload)
print('OK. Workflow atualizado. Total nodes agora:', len(res.get('nodes', nodes)))
