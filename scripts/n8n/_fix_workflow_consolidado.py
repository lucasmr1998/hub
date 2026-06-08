"""
Fix consolidado do workflow Vero — aplica TODAS as correcoes num PUT atomico:
1. Load Session: query com colunas reais (telefone, nodo_atual, dados)
2. Save Session: credencial correta + telefone via $node['Entrada']
3. Step nodes: .vars -> .dados nas merges
4. Enviar Wazapi: continueOnFail + onError
5. Enviar Lead Hubtrix: URL hardcoded (ja feito antes, garante de novo)
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

LOAD_QUERY = """SELECT telefone, nodo_atual, dados
FROM vero_session
WHERE telefone = '{{ $json.telefone }}'
UNION ALL
SELECT '{{ $json.telefone }}', 'inicio', '{}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM vero_session WHERE telefone = '{{ $json.telefone }}')
LIMIT 1;"""

SAVE_QUERY = """INSERT INTO vero_session (telefone, nodo_atual, dados, atualizado_em)
VALUES ('{{ $node['Entrada'].json.telefone }}', '{{ $json.proximo_nodo }}', '{{ JSON.stringify($json.novas_vars || {}) }}'::jsonb, NOW())
ON CONFLICT (telefone) DO UPDATE
  SET nodo_atual = EXCLUDED.nodo_atual,
      dados = EXCLUDED.dados,
      atualizado_em = NOW()
RETURNING telefone, nodo_atual;"""

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()
print(f"Pre-fix state: active={wf.get('active')}")

# 1. Acha credencial Postgres correta (Load Session)
load_cred = None
for n in wf['nodes']:
    if n.get('name') == 'Load Session':
        c = n.get('credentials', {}).get('postgres')
        # Use a credencial se existir, senao usa Postgres account 7 conhecida
        load_cred = c or {'id': 'tvjxTZBUAfRi1NgL', 'name': 'Postgres account 7'}
        break
print(f"Credencial Postgres: {load_cred}")

# 2. Patcha todos os nodos
changes = []
for n in wf['nodes']:
    name = n.get('name', '')

    if name == 'Load Session':
        n['parameters']['query'] = LOAD_QUERY
        n['credentials'] = {'postgres': load_cred}
        changes.append('Load Session query + credential')

    elif name == 'Save Session':
        n['parameters']['query'] = SAVE_QUERY
        n['credentials'] = {'postgres': load_cred}
        changes.append('Save Session query + credential')

    elif name.startswith('Step '):
        for a in n.get('parameters', {}).get('assignments', {}).get('assignments', []):
            if a.get('name') == 'novas_vars' and isinstance(a.get('value'), str):
                old = a['value']
                # Trocar .vars -> .dados (referencia ao Load Session)
                new = old.replace("['Load Session'].json.vars", "['Load Session'].json.dados")
                if old != new:
                    a['value'] = new
                    changes.append(f'{name} .vars->.dados')

    elif name == 'Enviar Wazapi':
        n['onError'] = 'continueRegularOutput'
        n['continueOnFail'] = True
        changes.append('Enviar Wazapi continueOnFail')

    elif name == 'Enviar Lead Hubtrix':
        # Garante URL hardcoded
        url = n.get('parameters', {}).get('url', '')
        if '$env' in url or 'app.hubtrix.com.br' not in url:
            n['parameters']['url'] = 'https://app.hubtrix.com.br/api/public/n8n/lead/'
            changes.append('Enviar Lead Hubtrix URL hardcoded')

print(f'\nMudancas a aplicar ({len(changes)}):')
for c in changes:
    print(f'  - {c}')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT status: {r.status_code}')
if r.status_code >= 300:
    print(f'BODY: {r.text[:500]}')
    raise SystemExit(1)
result = r.json()
print(f'updatedAt: {result.get("updatedAt")}')
print(f'active apos PUT: {result.get("active")}')

# Verificacao: relê e confere
r2 = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf2 = r2.json()
print('\n=== Verificacao pos-PUT ===')
for n in wf2['nodes']:
    name = n.get('name', '')
    if name == 'Load Session':
        q = n['parameters']['query'][:80].replace('\n', ' ')
        print(f'  Load Session query: {q!r}')
        print(f'  Load Session cred: {n.get("credentials")}')
    elif name == 'Save Session':
        q = n['parameters']['query'][:80].replace('\n', ' ')
        print(f'  Save Session query: {q!r}')
        print(f'  Save Session cred: {n.get("credentials")}')
    elif name == 'Enviar Wazapi':
        print(f'  Enviar Wazapi onError={n.get("onError")} continueOnFail={n.get("continueOnFail")}')
