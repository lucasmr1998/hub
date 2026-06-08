"""
Configura integracao Uazapi no workflow Vero:

1. Cria credencial HTTP Header Auth "Uazapi TR Carrion" com header 'token'
2. Atualiza nodo "Enviar Wazapi":
   - URL hardcoded https://consulteplus.uazapi.com/send/text
   - Body: { number, text }
   - Authentication via credencial
   - Remove continueOnFail (agora queremos ver erros)
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

UAZAPI_URL = 'https://consulteplus.uazapi.com'
UAZAPI_TOKEN = '9ef0cf61-87b3-444a-8769-07b0b74563e5'
CRED_NAME = 'Uazapi TR Carrion'

# === 1. Cria credencial ===
print(f'Criando credencial {CRED_NAME}...')
existing_creds = requests.get(f'{BASE}/api/v1/credentials', headers=HEADERS, timeout=15).json()
items = existing_creds.get('data', existing_creds) if isinstance(existing_creds, dict) else existing_creds
cred_id = None
for c in items:
    if c.get('name') == CRED_NAME:
        cred_id = c['id']
        print(f'  Ja existe: id={cred_id}')
        break

if not cred_id:
    r = requests.post(f'{BASE}/api/v1/credentials', headers=HEADERS, data=json.dumps({
        'name': CRED_NAME,
        'type': 'httpHeaderAuth',
        'data': {'name': 'token', 'value': UAZAPI_TOKEN},
    }), timeout=20)
    if r.status_code >= 300:
        print(f'ERRO criando credencial: {r.status_code} {r.text[:300]}')
        sys.exit(1)
    cred = r.json()
    cred_id = cred.get('id') or cred.get('data', {}).get('id')
    print(f'  Criada: id={cred_id}')

# === 2. Atualiza nodo Enviar Wazapi ===
r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

for n in wf['nodes']:
    if n.get('name') == 'Enviar Wazapi':
        n['parameters'] = {
            'method': 'POST',
            'url': f'{UAZAPI_URL}/send/text',
            'authentication': 'genericCredentialType',
            'genericAuthType': 'httpHeaderAuth',
            'sendHeaders': True,
            'headerParameters': {
                'parameters': [
                    {'name': 'Content-Type', 'value': 'application/json'}
                ]
            },
            'sendBody': True,
            'specifyBody': 'json',
            'jsonBody': ('={\n'
                         '  "number": "{{ $node[\'Entrada\'].json.telefone }}",\n'
                         '  "text":   "{{ $json.resposta_bot }}",\n'
                         '  "linkPreview": false\n'
                         '}'),
            'options': {'timeout': 10000},
        }
        n['credentials'] = {
            'httpHeaderAuth': {'id': str(cred_id), 'name': CRED_NAME}
        }
        # Remove continueOnFail — agora queremos detectar erros
        n.pop('continueOnFail', None)
        n.pop('onError', None)
        # Manter onError leve pra nao bloquear ENVIAR LEAD HUBTRIX se Uazapi falhar
        n['continueOnFail'] = True
        n['onError'] = 'continueRegularOutput'
        print(f'Enviar Wazapi configurado:')
        print(f'  URL: {n["parameters"]["url"]}')
        print(f'  Credencial: {CRED_NAME} (id={cred_id})')
        break

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code} updatedAt={r.json().get("updatedAt") if r.status_code<300 else r.text[:300]}')

# === 3. Sanity check: envia mensagem direto pra Uazapi ===
print(f'\n=== Sanity: testando POST direto pra Uazapi ===')
NUMERO_TESTE = '553181167572'  # numero conectado da instancia
r = requests.post(f'{UAZAPI_URL}/send/text',
                  headers={'token': UAZAPI_TOKEN, 'Content-Type': 'application/json'},
                  json={'number': NUMERO_TESTE, 'text': 'Teste de integracao Vero — pode ignorar.',
                        'linkPreview': False},
                  timeout=15)
print(f'  status={r.status_code}')
print(f'  body={r.text[:500]}')
