"""
Reordena: Load Session passa a rodar ANTES de RegistrarMsgCliente.

Motivo: RegistrarMsgCliente referencia $node['Load Session'].json.dados pra
enviar dados_lead pro Hubtrix atualizar o Lead a cada turno. Mas Load Session
rodava DEPOIS do RegistrarMsgCliente — a expressao falhava com "hasn't been
executed".

Topologia antes:
  Sou a Ultima?[0] -> RegistrarMsgCliente -> Load Session -> Consultar Hubtrix Estado

Topologia depois:
  Sou a Ultima?[0] -> Load Session -> RegistrarMsgCliente -> Consultar Hubtrix Estado
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
wf = r.json()
conns = wf['connections']

# Sou a Ultima? — branch 0 vai pra Load Session (antes ia pra RegistrarMsgCliente)
su = conns.get('Sou a Ultima?', {}).get('main', [])
if su and su[0]:
    for c in su[0]:
        if c.get('node') == 'RegistrarMsgCliente':
            c['node'] = 'Load Session'
            print('Sou a Ultima?[0]: RegistrarMsgCliente -> Load Session')

# Load Session — agora aponta pra RegistrarMsgCliente (antes ia pra Consultar Hubtrix Estado)
conns['Load Session'] = {'main': [[{'node': 'RegistrarMsgCliente', 'type': 'main', 'index': 0}]]}
print('Load Session -> RegistrarMsgCliente')

# RegistrarMsgCliente — agora aponta pra Consultar Hubtrix Estado (antes ia pra Load Session)
conns['RegistrarMsgCliente'] = {'main': [[{'node': 'Consultar Hubtrix Estado', 'type': 'main', 'index': 0}]]}
print('RegistrarMsgCliente -> Consultar Hubtrix Estado')

allowed = {'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
           'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
