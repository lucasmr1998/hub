"""
Adiciona 2 nodos HTTP no workflow Vero pra registrar mensagens no Inbox:

1. RegistrarMsgCliente — logo apos Entrada, antes do Load Session
   POST /inbox/mensagem/ com direcao=recebida
2. RegistrarMsgBot — apos PegarRespostaBot, antes do Enviar Wazapi
   POST /inbox/mensagem/ com direcao=enviada

Ambos usam credencial 'Hubtrix N8N Webhook' que ja existe.
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

CRED = {'httpHeaderAuth': {'id': 'ix3a5mNnIdesAZRz', 'name': 'Hubtrix N8N Webhook'}}

# Body pra registrar mensagem do cliente (recebida)
BODY_CLIENTE = ('={\n'
                '  "tenant_slug":   "tr-carrion",\n'
                '  "telefone":      {{ JSON.stringify($node[\'Entrada\'].json.telefone) }},\n'
                '  "conteudo":      {{ JSON.stringify($node[\'Entrada\'].json.mensagem || \'(midia)\') }},\n'
                '  "direcao":       "recebida",\n'
                '  "canal_identif": "553181167572",\n'
                '  "tipo_conteudo": "{{ $node[\'Entrada\'].json.tem_imagem ? \'imagem\' : \'texto\' }}",\n'
                '  "arquivo_url":   {{ JSON.stringify($node[\'Entrada\'].json.url_imagem || \'\') }}\n'
                '}')

# Body pra registrar resposta do bot (enviada)
BODY_BOT = ('={\n'
            '  "tenant_slug":      "tr-carrion",\n'
            '  "telefone":         {{ JSON.stringify($node[\'Entrada\'].json.telefone) }},\n'
            '  "conteudo":         {{ JSON.stringify($json.resposta_bot) }},\n'
            '  "direcao":          "enviada",\n'
            '  "canal_identif":    "553181167572",\n'
            '  "modo_atendimento": "{{ $json.nodo_atual === \'concluido\' ? \'finalizado_bot\' : \'bot\' }}"\n'
            '}')

NODES_NEW = [
    {
        "parameters": {
            "method": "POST",
            "url": "https://app.hubtrix.com.br/api/public/n8n/inbox/mensagem/",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": BODY_CLIENTE,
            "options": {"timeout": 10000},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [-1080, 100],
        "id": "inbox-msg-cliente",
        "name": "RegistrarMsgCliente",
        "credentials": CRED,
        "continueOnFail": True,
        "onError": "continueRegularOutput",
    },
    {
        "parameters": {
            "method": "POST",
            "url": "https://app.hubtrix.com.br/api/public/n8n/inbox/mensagem/",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": BODY_BOT,
            "options": {"timeout": 10000},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [2120, 100],
        "id": "inbox-msg-bot",
        "name": "RegistrarMsgBot",
        "credentials": CRED,
        "continueOnFail": True,
        "onError": "continueRegularOutput",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'RegistrarMsgCliente' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

conns = wf['connections']

# Inserir RegistrarMsgCliente entre Entrada e Load Session
# Antes: Entrada -> Load Session
# Depois: Entrada -> RegistrarMsgCliente -> Load Session
print(f"Entrada outputs atuais: {conns.get('Entrada', {}).get('main', [])}")
conns['Entrada'] = {'main': [[{'node': 'RegistrarMsgCliente', 'type': 'main', 'index': 0}]]}
conns['RegistrarMsgCliente'] = {'main': [[{'node': 'Load Session', 'type': 'main', 'index': 0}]]}

# Inserir RegistrarMsgBot entre PegarRespostaBot e Enviar Wazapi
# Atual: PegarRespostaBot -> [Enviar Wazapi, Finalizou?]
# Novo:  PegarRespostaBot -> RegistrarMsgBot -> [Enviar Wazapi, Finalizou?]
prb = conns.get('PegarRespostaBot', {}).get('main', [])
print(f"PegarRespostaBot outputs atuais: {prb}")
conns['PegarRespostaBot'] = {'main': [[{'node': 'RegistrarMsgBot', 'type': 'main', 'index': 0}]]}
conns['RegistrarMsgBot'] = {'main': [[
    {'node': 'Enviar Wazapi', 'type': 'main', 'index': 0},
    {'node': 'Finalizou?', 'type': 'main', 'index': 0},
]]}

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
print('\nFluxo: Entrada -> RegistrarMsgCliente -> Load Session ... PegarRespostaBot -> RegistrarMsgBot -> [Enviar Wazapi, Finalizou?]')
