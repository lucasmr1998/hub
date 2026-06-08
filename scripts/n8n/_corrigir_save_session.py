"""
Corrige nodo Save Session:
1. Credential errada (estava apontando pra 'wifeed' em vez de 'Postgres account 7' do banco_n8n)
2. Query usa $json.telefone que vira undefined apos os Set nodes; trocar por $node['Entrada'].json.telefone
"""
import json
import requests
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}
WF_ID = 'Df1BgcXdg3HAUZwf'

NEW_SAVE_QUERY = """INSERT INTO vero_session (telefone, nodo_atual, dados, atualizado_em)
VALUES ('{{ $node['Entrada'].json.telefone }}', '{{ $json.proximo_nodo }}', '{{ JSON.stringify($json.novas_vars || {}) }}'::jsonb, NOW())
ON CONFLICT (telefone) DO UPDATE
  SET nodo_atual = EXCLUDED.nodo_atual,
      dados = EXCLUDED.dados,
      atualizado_em = NOW()
RETURNING telefone, nodo_atual;"""

# Tambem corrigir a query de Load Session pra ser robusta
NEW_LOAD_QUERY = """SELECT telefone, nodo_atual, dados
FROM vero_session
WHERE telefone = '{{ $json.telefone }}'
UNION ALL
SELECT '{{ $json.telefone }}', 'inicio', '{}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM vero_session WHERE telefone = '{{ $json.telefone }}')
LIMIT 1;"""

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

# Acha credential id do Load Session pra reaplicar no Save Session
load_cred = None
for n in wf['nodes']:
    if n.get('name') == 'Load Session':
        load_cred = n.get('credentials', {}).get('postgres')
        print(f'Credencial do Load Session: {load_cred}')
        break

if not load_cred:
    raise SystemExit('Load Session sem credential — investigar.')

# Patcha Save Session
for n in wf['nodes']:
    if n.get('name') == 'Save Session':
        old_cred = n.get('credentials', {}).get('postgres')
        n['credentials'] = {'postgres': load_cred}
        n['parameters']['query'] = NEW_SAVE_QUERY
        print(f'Save Session: trocou credential {old_cred} -> {load_cred}')
    elif n.get('name') == 'Load Session':
        n['parameters']['query'] = NEW_LOAD_QUERY

# Tambem patcha Enviar Lead Hubtrix pra ler telefone do Entrada
for n in wf['nodes']:
    if n.get('name') == 'Enviar Lead Hubtrix':
        body = n['parameters'].get('jsonBody', '')
        # Substitui referencias diretas a $node['Entrada'] no body se necessario
        print(f'\nEnviar Lead Hubtrix jsonBody (snippet):\n{body[:300]}')

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
