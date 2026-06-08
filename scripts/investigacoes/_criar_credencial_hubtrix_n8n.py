"""
Cria a credencial 'Hubtrix N8N Webhook' (HTTP Header Auth) no N8N via API.
Depois associa ao nodo 'Enviar Lead Hubtrix' do workflow Vero.
"""
import json
import requests
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
SECRET = env['HUBTRIX_N8N_WEBHOOK_SECRET']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}

WF_ID = 'Df1BgcXdg3HAUZwf'
CRED_NAME = 'Hubtrix N8N Webhook'

# 1. Lista credenciais existentes pra ver se ja existe
def list_credentials():
    # endpoint pode estar em /credentials ou /credentials/?...
    for url in [f'{BASE}/api/v1/credentials', f'{BASE}/api/v1/credentials/']:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
    return None

print('Listando credenciais existentes...')
existing = list_credentials()
if existing is None:
    print('  Endpoint GET /credentials nao disponivel (esperado em algumas versoes).')
    cred_id = None
else:
    data = existing.get('data', existing) if isinstance(existing, dict) else existing
    print(f'  {len(data)} credenciais.')
    cred_id = None
    for c in data:
        if c.get('name') == CRED_NAME:
            cred_id = c['id']
            print(f"  Ja existe: id={cred_id}")
            break

# 2. Cria a credencial se nao existir
if not cred_id:
    print(f'\nCriando credencial {CRED_NAME!r}...')
    payload = {
        'name': CRED_NAME,
        'type': 'httpHeaderAuth',
        'data': {
            'name': 'X-N8N-Webhook-Secret',
            'value': SECRET,
        },
    }
    r = requests.post(f'{BASE}/api/v1/credentials', headers=HEADERS, data=json.dumps(payload), timeout=20)
    print(f'  status={r.status_code}')
    if r.status_code >= 300:
        print(f'  body={r.text[:500]}')
        raise SystemExit(1)
    cred = r.json()
    cred_id = cred.get('id') or cred.get('data', {}).get('id')
    print(f'  OK. id={cred_id}')

# 3. Patcha o nodo do workflow pra referenciar a credencial
print('\nAssociando credencial ao nodo Enviar Lead Hubtrix...')
r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

for n in wf['nodes']:
    if n.get('name') == 'Enviar Lead Hubtrix':
        n['credentials'] = {
            'httpHeaderAuth': {'id': str(cred_id), 'name': CRED_NAME}
        }
        print(f'  Nodo atualizado com credentials: {n["credentials"]}')
        break

allowed_settings_keys = {
    'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
    'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone',
    'executionOrder',
}
src_settings = wf.get('settings') or {}
clean_settings = {k: v for k, v in src_settings.items() if k in allowed_settings_keys}

payload = {
    'name': wf['name'],
    'nodes': wf['nodes'],
    'connections': wf['connections'],
    'settings': clean_settings,
}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
if r.status_code >= 300:
    print(f'STATUS: {r.status_code}')
    print(f'BODY: {r.text[:500]}')
    raise SystemExit(1)
print(f'\nWorkflow atualizado. updatedAt: {r.json().get("updatedAt")}')
print(f'Credencial {CRED_NAME!r} (id={cred_id}) associada ao nodo "Enviar Lead Hubtrix".')
