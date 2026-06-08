"""
Adiciona handoff humano:
1. DetectarPedidoHumano (code) — detecta keywords E conta tentativas no mesmo estado
2. Step Aguarda Humano (Set) — anota, marca conversa modo=humano
3. Nova rule aguarda_humano no Switch
4. Atualiza PegarRespostaBot com novo Step
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

# Code que detecta pedido de humano OU 3 tentativas seguidas no mesmo estado
DETECTAR_HUMANO_CODE = '''// DetectarPedidoHumano — sobrescreve nodo_atual='aguarda_humano' se necessario
const ss = $input.first().json;
let mensagem = '';
try { mensagem = String($('Entrada').first().json.mensagem || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, ''); } catch(e) {}

const KEYWORDS_HUMANO = [
  'atendente', 'vendedor', 'humano', 'pessoa', 'consultor', 'operador',
  'falar com voce', 'falar com alguem', 'ajuda', 'socorro',
  'nao consigo', 'nao tenho', 'sem foto', 'sem rg', 'sem cnh',
  'depois', 'mais tarde', 'desisto', 'desistir',
  'cancelar', 'cancela',
];

const pediu_humano = KEYWORDS_HUMANO.some(k => mensagem.includes(k));

// Conta tentativas: se cliente nao avancou no MESMO estado >= 3x, transfere
const dados = ss.dados || {};
const estado_atual = ss.nodo_atual;
const tentativas_key = `_tentativas_${estado_atual}`;
const tentativas = (dados[tentativas_key] || 0) + 1;
const muito_erro = tentativas >= 3;

if (pediu_humano || muito_erro) {
  return [{ json: {
    ...ss,
    nodo_atual: 'aguarda_humano',
    dados: {
      ...dados,
      motivo_handoff: pediu_humano ? 'cliente_pediu' : 'muitas_tentativas',
      estado_anterior: estado_atual,
      mensagem_handoff: mensagem.slice(0, 200),
    }
  }}];
}

// senao, incrementa contador do estado atual
return [{ json: {
  ...ss,
  dados: { ...dados, [tentativas_key]: tentativas }
}}];'''

# Step Aguarda Humano — bot responde aviso, modo Inbox vira humano
NODES_NEW = [
    {
        "parameters": {"jsCode": DETECTAR_HUMANO_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-720, 0],
        "id": "detectar-humano",
        "name": "DetectarPedidoHumano",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sh1", "name": "resposta_bot",
                     "value": ("=Tudo bem! 😊 Vou anotar suas informacoes e em alguns minutos um "
                               "consultor da Vero entra em contato direto contigo por aqui.\n\n"
                               "Pode mandar qualquer detalhe extra que ja deixo guardado pro vendedor."),
                     "type": "string"},
                    {"id": "sh2", "name": "proximo_nodo", "value": "aguarda_humano", "type": "string"},
                    {"id": "sh3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "sh4", "name": "deve_enviar_hubtrix", "value": "=true", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-480, 1100],
        "id": "step-aguarda-humano",
        "name": "Step Aguarda Humano",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'DetectarPedidoHumano' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Inserir DetectarPedidoHumano ENTRE DetectarReset e Por Nodo Atual
conns = wf['connections']
conns['DetectarReset'] = {'main': [[{'node': 'DetectarPedidoHumano', 'type': 'main', 'index': 0}]]}
conns['DetectarPedidoHumano'] = {'main': [[{'node': 'Por Nodo Atual', 'type': 'main', 'index': 0}]]}
print('Fluxo: ... Load Session -> DetectarReset -> DetectarPedidoHumano -> Por Nodo Atual')

# Switch: add rule aguarda_humano
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
rules = switch_node['parameters']['rules']['values']
keys = {r.get('outputKey') for r in rules}
if 'aguarda_humano' not in keys:
    rules.append({
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "sw-humano",
                "leftValue": "={{ $json.nodo_atual }}",
                "rightValue": "aguarda_humano",
                "operator": {"type": "string", "operation": "equals"},
            }],
            "combinator": "and",
        },
        "renameOutput": True,
        "outputKey": "aguarda_humano",
    })
    print('Switch: adicionada rule aguarda_humano')

switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
while len(switch_outs) < len(rules):
    switch_outs.append([])
for i, rule in enumerate(rules):
    if rule.get('outputKey') == 'aguarda_humano':
        switch_outs[i] = [{'node': 'Step Aguarda Humano', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]=aguarda_humano -> Step Aguarda Humano')

conns['Step Aguarda Humano'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# PegarRespostaBot: incluir Step Aguarda Humano
for n in wf['nodes']:
    if n.get('name') == 'PegarRespostaBot':
        code = n['parameters']['jsCode']
        if 'Step Aguarda Humano' not in code:
            code = code.replace("'Step Inicio',", "'Step Aguarda Humano', 'Step Inicio',")
            n['parameters']['jsCode'] = code
            print('PegarRespostaBot: incluido Step Aguarda Humano')

# Atualizar nodo RegistrarMsgBot pra mandar modo='humano' quando estado eh aguarda_humano
NEW_BODY_INBOX_BOT = ('={\n'
                      '  "tenant_slug":      "tr-carrion",\n'
                      '  "telefone":         {{ JSON.stringify($node[\'Entrada\'].json.telefone) }},\n'
                      '  "conteudo":         {{ JSON.stringify($node[\'PegarRespostaBot\'].json.resposta_bot) }},\n'
                      '  "direcao":          "enviada",\n'
                      '  "canal_identif":    "553181167572",\n'
                      '  "modo_atendimento": "{{ (() => { const n = $node[\'PegarRespostaBot\'].json.nodo_atual; if (n === \'concluido\') return \'finalizado_bot\'; if (n === \'aguarda_humano\') return \'humano\'; return \'bot\'; })() }}"\n'
                      '}')
for n in wf['nodes']:
    if n.get('name') == 'RegistrarMsgBot':
        n['parameters']['jsonBody'] = NEW_BODY_INBOX_BOT
        print('RegistrarMsgBot: agora seta modo=humano quando estado=aguarda_humano')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
print('\nHandoff humano implementado:')
print('  - Keywords: atendente/vendedor/humano/ajuda/sem foto/desisto/cancelar/etc.')
print('  - Tentativas: >= 3 no mesmo estado vira aguarda_humano')
print('  - Inbox Conversa marcada como modo=humano')
