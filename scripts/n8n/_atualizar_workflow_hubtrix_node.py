"""
Atualiza o nodo 'Enviar Lead Hubtrix' do workflow Vero no N8N pra:
- URL hardcoded (sem $env.HUBTRIX_URL)
- Autenticacao via Generic Credential Type / HTTP Header Auth
  (usuario cria a credencial 'Hubtrix N8N Webhook' na UI e seleciona no nodo)
- Remove parametro de header manual (vai ser injetado pela credencial)
"""
import json
import requests
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}

WF_ID = 'Df1BgcXdg3HAUZwf'

def get_wf():
    r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def put_wf(wf):
    # N8N PUT exige payload com nodes/connections/settings; remove campos read-only
    # 'settings' tem props extras que falham na validacao — filtra so as permitidas
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
        print('STATUS:', r.status_code)
        print('BODY:', r.text[:1000])
    r.raise_for_status()
    return r.json()

wf = get_wf()
print(f"Workflow: {wf['name']}  (active={wf['active']})")

# Acha e patcha o nodo
for n in wf['nodes']:
    if n.get('name') == 'Enviar Lead Hubtrix':
        print('Patchando nodo Enviar Lead Hubtrix...')

        # Mantem o jsonBody, mas troca URL + auth
        n['parameters']['url'] = 'https://app.hubtrix.com.br/api/public/n8n/lead/'
        n['parameters']['authentication'] = 'genericCredentialType'
        n['parameters']['genericAuthType'] = 'httpHeaderAuth'

        # Remove o header manual de secret; mantem so o Content-Type
        n['parameters']['sendHeaders'] = True
        n['parameters']['headerParameters'] = {
            'parameters': [
                {'name': 'Content-Type', 'value': 'application/json'}
            ]
        }

        # credentials sera setado pelo usuario na UI (precisa do ID gerado quando criar a credencial)
        # Por enquanto deixa vazio — N8N vai mostrar dropdown vazio pro usuario escolher
        n.pop('credentials', None)

        print(json.dumps(n, indent=2, ensure_ascii=False))
        break
else:
    raise SystemExit('Nodo nao encontrado!')

result = put_wf(wf)
print('\nUpdate OK. Novo updatedAt:', result.get('updatedAt'))
print('\nPROXIMO PASSO PRO USUARIO:')
print('  1. N8N -> Credentials -> New')
print('  2. Type: HTTP Header Auth')
print('  3. Name: Hubtrix N8N Webhook')
print('  4. Header Name: X-N8N-Webhook-Secret')
print('  5. Header Value: 1TDwKubueobLDJEMYmxVAmnkp5jTzbs9R-C9FW3B1OY')
print('  6. Save')
print('  7. Abrir workflow [Vero] Orquestrador Atendimento')
print('  8. Abrir nodo "Enviar Lead Hubtrix"')
print('  9. No campo Credential to connect with: escolher "Hubtrix N8N Webhook"')
print(' 10. Save + Active')
