"""
Fix final no nodo Enviar Lead Hubtrix:
- Remove header X-N8N-Webhook-Secret (vem da credencial)
- Garante authentication=genericCredentialType + httpHeaderAuth + credentials apontando pra Hubtrix N8N Webhook
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
CRED_ID = 'ix3a5mNnIdesAZRz'  # Hubtrix N8N Webhook
CRED_NAME = 'Hubtrix N8N Webhook'

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

for n in wf['nodes']:
    if n.get('name') == 'Enviar Lead Hubtrix':
        p = n['parameters']

        p['url'] = 'https://app.hubtrix.com.br/api/public/n8n/lead/'
        p['authentication'] = 'genericCredentialType'
        p['genericAuthType'] = 'httpHeaderAuth'

        # Remove o header X-N8N-Webhook-Secret e mantem so o Content-Type
        p['sendHeaders'] = True
        p['headerParameters'] = {
            'parameters': [
                {'name': 'Content-Type', 'value': 'application/json'}
            ]
        }

        # Associa credencial
        n['credentials'] = {
            'httpHeaderAuth': {'id': CRED_ID, 'name': CRED_NAME}
        }

        print('Nodo Enviar Lead Hubtrix patchado:')
        print(json.dumps({
            'url': p['url'],
            'auth': p['authentication'],
            'genericAuthType': p['genericAuthType'],
            'headers': p['headerParameters'],
            'credentials': n['credentials'],
        }, indent=2, ensure_ascii=False))
        break

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT status: {r.status_code}')
if r.status_code >= 300:
    print(f'BODY: {r.text[:500]}')
else:
    print(f'updatedAt: {r.json().get("updatedAt")}')
