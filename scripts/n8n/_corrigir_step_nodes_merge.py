"""
Corrige Step nodes e Enviar Wazapi:
1. Step nodes: trocar $node['Load Session'].json.vars -> .dados (porque a coluna se chama dados)
2. Enviar Wazapi: marcar continueOnFail/onError=continueRegularOutput (env access bloqueado)
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

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

patched = 0
for n in wf['nodes']:
    name = n.get('name', '')

    # Step nodes: substituir .vars -> .dados
    if name.startswith('Step '):
        assignments = n.get('parameters', {}).get('assignments', {}).get('assignments', [])
        for a in assignments:
            if a.get('name') == 'novas_vars' and isinstance(a.get('value'), str):
                old = a['value']
                new = old.replace("['Load Session'].json.vars", "['Load Session'].json.dados")
                if old != new:
                    a['value'] = new
                    patched += 1
                    print(f"  {name}: ajustada referencia .vars -> .dados")

    # Enviar Wazapi: continueOnFail (env access ta bloqueado e a gente nao precisa
    # de Wazapi pra simular o fluxo — vai falhar mas o fluxo segue ate Hubtrix)
    if name == 'Enviar Wazapi':
        n['onError'] = 'continueRegularOutput'
        # Em algumas versoes a flag e `continueOnFail`
        n['continueOnFail'] = True
        print(f"  {name}: setado onError=continueRegularOutput + continueOnFail=true")
        patched += 1

print(f'\n{patched} nodos patchados.')

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
