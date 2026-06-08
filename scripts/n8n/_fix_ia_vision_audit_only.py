"""
IA Vision RG: volta pro modo AUDIT-ONLY.

Antes: IF 'RG Frente IA OK?' / 'RG Verso IA OK?' exigiam
   is_documento=true AND legivel=true
e desviavam pra reasking se IA Vision rejeitasse OU desse erro.

Resultado: cliente bloqueado quando IA Vision falhava (API down, erro de
parse, etc.) ou quando IA acertadamente rejeitava (mas user quer aceitar
e auditar depois).

Depois: IF sempre TRUE. Veredito da IA fica capturado no proprio output
do node IA Vision RG Frente/Verso e pode ser lido a posteriori via
exec data. Para tracking persistente, futuro fix: salvar em dados_custom
no Step Aguarda RG Frente/Verso.
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

ALVOS = {'RG Frente IA OK?', 'RG Verso IA OK?'}

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

mudou = 0
for n in wf['nodes']:
    if n.get('name') in ALVOS:
        conds = n['parameters'].get('conditions', {}).get('conditions', [])
        if conds:
            # Substitui a expressao por literal true — sempre passa
            conds[0]['leftValue'] = '={{ true }}'
            conds[0]['rightValue'] = ''
            conds[0]['operator'] = {'type': 'boolean', 'operation': 'true', 'singleValue': True}
            print(f'  {n["name"]}: condicao trocada pra sempre TRUE (audit-only)')
            mudou += 1

# Garante que IA Vision nodes nao quebram o flow se der erro
for n in wf['nodes']:
    if n.get('name') in ('IA Vision RG Frente', 'IA Vision RG Verso'):
        if not n.get('continueOnFail'):
            n['continueOnFail'] = True
            print(f'  {n["name"]}: continueOnFail=true (nao quebra flow se OpenAI falhar)')
            mudou += 1

if not mudou:
    print('Nada pra mudar.')
    sys.exit(0)

allowed = {'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
           'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
else:
    print(f'\n{mudou} ajuste(s) aplicado(s).')
