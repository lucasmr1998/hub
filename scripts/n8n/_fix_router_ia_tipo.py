"""
Corrige os Routers IA Tipo (Switch) pra usar expressao com tratamento de erro,
ja que $node['X'] dispara erro se X nao foi executado naquele run.
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

# Expressao IIFE que captura tipo, retornando '' se nodo nao executou
EXPR_TIPO = ("={{ (() => { "
             "try { return $('Contexto Email').first().json.tipo; } catch(e) {} "
             "try { return $('Contexto CEP').first().json.tipo; } catch(e) {} "
             "return ''; "
             "})() }}")

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

patched = 0
for n in wf['nodes']:
    if n.get('name') in ('Router IA Tipo', 'Router IA Tipo Erro'):
        rules = n['parameters']['rules']['values']
        for rule in rules:
            for cond in rule['conditions']['conditions']:
                cond['leftValue'] = EXPR_TIPO
        patched += 1
        print(f'Patched: {n["name"]}')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code} updatedAt={r.json().get("updatedAt") if r.status_code<300 else r.text[:200]}')
