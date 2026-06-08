"""
Corrige queries dos nodos Postgres do workflow Vero pra bater com a tabela vero_session
real (PK telefone, coluna dados jsonb — nao 'id' nem 'vars').

Procura nodos com type postgres e patcha o parameter 'query'.
"""
import json
import requests
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}
WF_ID = 'Df1BgcXdg3HAUZwf'

LOAD_QUERY = """SELECT telefone, nodo_atual, dados
FROM vero_session
WHERE telefone = '{{ $json.telefone }}'
UNION ALL
SELECT '{{ $json.telefone }}', 'inicio', '{}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM vero_session WHERE telefone = '{{ $json.telefone }}')
LIMIT 1;"""

SAVE_QUERY = """INSERT INTO vero_session (telefone, nodo_atual, dados, atualizado_em)
VALUES ('{{ $json.telefone }}', '{{ $json.proximo_nodo }}', '{{ JSON.stringify($json.novas_vars || {}) }}'::jsonb, NOW())
ON CONFLICT (telefone) DO UPDATE
  SET nodo_atual = EXCLUDED.nodo_atual,
      dados = EXCLUDED.dados,
      atualizado_em = NOW()
RETURNING telefone, nodo_atual;"""

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

patched = 0
for n in wf['nodes']:
    if n.get('name') == 'Load Session':
        n['parameters']['query'] = LOAD_QUERY
        print(f'  patched Load Session')
        patched += 1
    elif n.get('name') == 'Save Session':
        n['parameters']['query'] = SAVE_QUERY
        print(f'  patched Save Session')
        patched += 1

print(f'\n{patched} nodos atualizados.')

# PUT
allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT status: {r.status_code}')
if r.status_code >= 300:
    print(f'BODY: {r.text[:500]}')
else:
    print(f'updatedAt: {r.json().get("updatedAt")}')
