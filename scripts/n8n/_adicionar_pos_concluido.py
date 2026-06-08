"""
B.2: Cliente em estado=concluido manda mensagem → bot pergunta se quer novo pedido.

Adiciona:
- Estado aguarda_decisao_pos_concluido
- Step "Pergunta Pos Concluido" (bot pergunta se quer novo)
- Reusa ClassificarConfirmacao (sim/nao)
- Sim → reseta sessao (estado=inicio, dados={})
- Nao → aguarda_humano
"""
import json
import sys
import io
import requests
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}
WF_ID = 'Df1BgcXdg3HAUZwf'

NODES_NEW = [
    # Switch[concluido] -> Step Pergunta Pos Concluido
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "spc1", "name": "resposta_bot",
                     "value": ("=Oi {{ $node['Load Session'].json.dados.nome || '' }}! 😊\n\n"
                               "Vi que voce ja preencheu o cadastro hoje. Quer comecar um novo pedido ou "
                               "prefere falar com um consultor?"),
                     "type": "string"},
                    {"id": "spc2", "name": "proximo_nodo", "value": "aguarda_decisao_pos_concluido", "type": "string"},
                    {"id": "spc3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "spc4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-480, 1200],
        "id": "step-pergunta-pos-concluido",
        "name": "Step Pergunta Pos Concluido",
    },
    # ClassificarPosConcluido (reusa same lib + adiciona "novo" como sim, "consultor" como humano)
    {
        "parameters": {"jsCode": '''// ClassificarPosConcluido — sim (novo pedido) / nao (humano)
let raw = '';
try { raw = $('Entrada').first().json.mensagem || ''; } catch(e) {}
const m = String(raw).trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
const NOVO = ['sim','s','novo','novo pedido','quero','outro','recomecar','recomeçar','reiniciar','de novo'];
const HUMANO = ['nao','n','consultor','humano','atendente','vendedor','falar com','pessoa'];
let r = 'unknown';
if (NOVO.some(w => m === w || m.startsWith(w + ' '))) r = 'novo';
else if (HUMANO.some(w => m === w || m.startsWith(w + ' '))) r = 'humano';
return [{ json: { confirmacao: r } }];'''},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-720, 1300],
        "id": "classificar-pos-concluido",
        "name": "ClassificarPosConcluido",
    },
    # Switch: sim/humano/fallback
    {
        "parameters": {
            "rules": {"values": [
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "pc-sim", "leftValue": "={{ $json.confirmacao }}", "rightValue": "novo",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "novo"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "pc-humano", "leftValue": "={{ $json.confirmacao }}", "rightValue": "humano",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "humano"},
            ]},
            "looseTypeValidation": True, "options": {"fallbackOutput": "extra"},
        },
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [-480, 1300],
        "id": "switch-pos-concluido",
        "name": "Decisao Pos Concluido?",
    },
    # Step Reset (sim: reinicia sessao)
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "spr1", "name": "resposta_bot",
                     "value": "Otimo! Vamos comecar um novo pedido. Qual o seu nome?",
                     "type": "string"},
                    {"id": "spr2", "name": "proximo_nodo", "value": "aguarda_nome", "type": "string"},
                    {"id": "spr3", "name": "novas_vars", "value": "={{ ({}) }}", "type": "object"},
                    {"id": "spr4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-240, 1250],
        "id": "step-novo-pedido",
        "name": "Step Novo Pedido",
    },
    # Step Humano Pos Concluido (nao: handoff)
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "shpc1", "name": "resposta_bot",
                     "value": "Tudo bem! Vou passar pra um consultor te ajudar. Em alguns minutos ele entra em contato.",
                     "type": "string"},
                    {"id": "shpc2", "name": "proximo_nodo", "value": "aguarda_humano", "type": "string"},
                    {"id": "shpc3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "shpc4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-240, 1350],
        "id": "step-humano-pos-concluido",
        "name": "Step Humano Pos Concluido",
    },
    # Reasking
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "srpc1", "name": "resposta_bot",
                     "value": "Nao entendi 😅 Responde 'novo pedido' pra recomecar ou 'consultor' pra falar com humano.",
                     "type": "string"},
                    {"id": "srpc2", "name": "proximo_nodo", "value": "aguarda_decisao_pos_concluido", "type": "string"},
                    {"id": "srpc3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "srpc4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-240, 1450],
        "id": "step-reasking-pos-concluido",
        "name": "Step Reasking Pos Concluido",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()
existing = {n['name'] for n in wf['nodes']}
if 'Step Pergunta Pos Concluido' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Switch — adicionar rules 'concluido' e 'aguarda_decisao_pos_concluido'
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
rules = switch_node['parameters']['rules']['values']
keys = {r.get('outputKey') for r in rules}
for novo in ['concluido', 'aguarda_decisao_pos_concluido']:
    if novo not in keys:
        rules.append({
            "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
             "conditions": [{"id": f"sw-{novo}", "leftValue": "={{ $json.nodo_atual }}", "rightValue": novo,
                             "operator": {"type": "string", "operation": "equals"}}],
             "combinator": "and"},
            "renameOutput": True, "outputKey": novo,
        })
        print(f'Switch: adicionada rule {novo}')

# Connections
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
while len(switch_outs) < len(rules):
    switch_outs.append([])
for i, rule in enumerate(rules):
    if rule.get('outputKey') == 'concluido':
        switch_outs[i] = [{'node': 'Step Pergunta Pos Concluido', 'type': 'main', 'index': 0}]
    elif rule.get('outputKey') == 'aguarda_decisao_pos_concluido':
        switch_outs[i] = [{'node': 'ClassificarPosConcluido', 'type': 'main', 'index': 0}]

conns['Step Pergunta Pos Concluido'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['ClassificarPosConcluido'] = {'main': [[{'node': 'Decisao Pos Concluido?', 'type': 'main', 'index': 0}]]}
conns['Decisao Pos Concluido?'] = {'main': [
    [{'node': 'Step Novo Pedido', 'type': 'main', 'index': 0}],
    [{'node': 'Step Humano Pos Concluido', 'type': 'main', 'index': 0}],
    [{'node': 'Step Reasking Pos Concluido', 'type': 'main', 'index': 0}],
]}
conns['Step Novo Pedido'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Humano Pos Concluido'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking Pos Concluido'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# Atualizar PegarRespostaBot
for n in wf['nodes']:
    if n.get('name') == 'PegarRespostaBot':
        code = n['parameters']['jsCode']
        if 'Step Pergunta Pos Concluido' not in code:
            code = code.replace("'Step Inicio',",
                "'Step Pergunta Pos Concluido', 'Step Novo Pedido', 'Step Humano Pos Concluido', 'Step Reasking Pos Concluido', 'Step Inicio',")
            n['parameters']['jsCode'] = code
            print('PegarRespostaBot: incluidos 4 steps pos-concluido')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
print('\nB.2 implementado: cliente concluido manda msg -> bot pergunta "novo pedido ou consultor?"')
