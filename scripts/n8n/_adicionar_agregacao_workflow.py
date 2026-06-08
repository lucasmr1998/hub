"""
C.3 simplificado: debouncing (newest-wins).

Cliente manda 3 msgs em 5s → bot processa apenas a ULTIMA (mais recente).
As anteriores sao dropadas silenciosamente.

Nodos novos (apos Entrada, antes de RegistrarMsgCliente):
1. BufferInserir (Postgres) — INSERT msg no vero_message_buffer
2. Aguardar 2s (Wait)
3. Ser Ultima Query (Postgres) — SELECT max(id) pra mesma sessao
4. Sou a Ultima? (IF) — true: segue / false: descarta

Sem renomeacao. Sem agregacao real. Apenas debounce.
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

POSTGRES_CRED = {'postgres': {'id': 'tvjxTZBUAfRi1NgL', 'name': 'Postgres account 7'}}

NODES_NEW = [
    {
        "parameters": {
            "operation": "executeQuery",
            "query": ("INSERT INTO vero_message_buffer (telefone, conteudo, tem_imagem, url_imagem) "
                      "VALUES ('{{ $node['Entrada'].json.telefone }}', "
                      "'{{ String($node['Entrada'].json.mensagem || '').replace(/'/g, chr(39) + chr(39)) }}', "
                      "{{ $node['Entrada'].json.tem_imagem ? 'TRUE' : 'FALSE' }}, "
                      "'{{ $node['Entrada'].json.url_imagem || '' }}') "
                      "RETURNING id;"),
            "options": {},
        },
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": [-1280, -100],
        "id": "buffer-insert",
        "name": "BufferInserir",
        "credentials": POSTGRES_CRED,
    },
    {
        "parameters": {"amount": 2, "unit": "seconds"},
        "type": "n8n-nodes-base.wait",
        "typeVersion": 1.1,
        "position": [-1200, -100],
        "id": "aguarda-2s",
        "name": "Aguardar 2s",
        "webhookId": "wait-buffer-vero",
    },
    {
        "parameters": {
            "operation": "executeQuery",
            "query": ("SELECT MAX(id) AS max_id FROM vero_message_buffer "
                      "WHERE telefone = '{{ $node['Entrada'].json.telefone }}' "
                      "AND recebida_em > NOW() - INTERVAL '10 seconds';"),
            "options": {},
        },
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": [-1120, -100],
        "id": "ser-ultima-query",
        "name": "Ser Ultima Query",
        "credentials": POSTGRES_CRED,
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "su-1",
                    "leftValue": "={{ Number($json.max_id) }}",
                    "rightValue": "={{ Number($node['BufferInserir'].json.id) }}",
                    "operator": {"type": "number", "operation": "equals"},
                }],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [-1040, -100],
        "id": "sou-ultima",
        "name": "Sou a Ultima?",
    },
    {
        "parameters": {"options": {"responseCode": 200}, "respondWith": "text", "responseBody": "buffered"},
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.4,
        "position": [-960, 100],
        "id": "respond-buffered",
        "name": "Respond Buffered",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()
existing = {n['name'] for n in wf['nodes']}
if 'BufferInserir' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

conns = wf['connections']
# Antes: Entrada -> RegistrarMsgCliente
# Depois: Entrada -> BufferInserir -> Aguardar 2s -> SerUltimaQuery -> SouUltima? -> (true: RegistrarMsgCliente / false: Respond Buffered)
conns['Entrada'] = {'main': [[{'node': 'BufferInserir', 'type': 'main', 'index': 0}]]}
conns['BufferInserir'] = {'main': [[{'node': 'Aguardar 2s', 'type': 'main', 'index': 0}]]}
conns['Aguardar 2s'] = {'main': [[{'node': 'Ser Ultima Query', 'type': 'main', 'index': 0}]]}
conns['Ser Ultima Query'] = {'main': [[{'node': 'Sou a Ultima?', 'type': 'main', 'index': 0}]]}
conns['Sou a Ultima?'] = {'main': [
    [{'node': 'RegistrarMsgCliente', 'type': 'main', 'index': 0}],
    [{'node': 'Respond Buffered', 'type': 'main', 'index': 0}],
]}

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT {r.status_code}')
print('\nC.3 (debouncing newest-wins) implementado:')
print('  Cliente manda 3 msgs em 5s -> bot processa apenas a ultima.')
print('  Anteriores sao silenciosamente dropadas (respond=buffered).')
