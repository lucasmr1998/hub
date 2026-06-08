"""
Aumenta timeout e adiciona retry nos nodos HTTP que chamam Uazapi.

Antes:
  Enviar Wazapi / Enviar Typing: timeout=10000ms, sem retry
  -> timeout em horario de pico = mensagem perdida silenciosamente

Depois:
  timeout=20000ms
  retryOnFail=true, maxTries=3, waitBetweenTries=2000ms
  continueOnFail=true (preservado — nao quebra o fluxo se falhar de novo)
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

# Alvo: nodos HTTP que chamam Uazapi (envio + typing + presence etc.)
ALVOS = {'Enviar Wazapi', 'Enviar Typing'}

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

mudou = 0
for n in wf['nodes']:
    if n.get('name') in ALVOS and n.get('type') == 'n8n-nodes-base.httpRequest':
        # 1. timeout
        opts = n['parameters'].setdefault('options', {})
        old_timeout = opts.get('timeout', 10000)
        opts['timeout'] = 20000

        # 2. retry no nivel do nodo (n8n suporta direto no objeto do nodo)
        n['retryOnFail'] = True
        n['maxTries'] = 3
        n['waitBetweenTries'] = 2000
        # continueOnFail ja existe, mantem
        n['continueOnFail'] = True

        print(f'  {n["name"]}: timeout {old_timeout}->20000, retry 3x com 2s')
        mudou += 1

if not mudou:
    print('Nenhum nodo alvo encontrado.')
    sys.exit(1)

allowed = {'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
           'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
else:
    print(f'\n{mudou} nodo(s) atualizados.')
