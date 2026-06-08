"""Atualiza apenas o jsCode do nodo ValidarEmail no workflow."""
import json, sys, io, requests
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}
WF_ID = 'Df1BgcXdg3HAUZwf'

EMAIL_CODE = '''// ValidarEmail — adaptado do Matrix
// Le a mensagem do nodo Entrada (no ponto do fluxo $json e a saida do Switch, sem campo mensagem)
const mensagem = $('Entrada').first().json.mensagem;
for (const item of $input.all()) {
  const emailString = mensagem ? String(mensagem).trim() : null;
  item.json.isValidEmail = false;
  item.json.validationError = null;

  if (!emailString) {
    item.json.validationError = "Email vazio";
    continue;
  }

  const regex = /^(([^<>()[\\]\\\\.,;:\\s@"]+(\\.[^<>()[\\]\\\\.,;:\\s@"]+)*)|(".+"))@((\\[[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\])|(([a-zA-Z\\-0-9]+\\.)+[a-zA-Z]{2,}))$/;

  if (!regex.test(emailString)) {
    item.json.validationError = "Formato de email invalido";
    continue;
  }

  item.json.isValidEmail = true;
}
return $input.all();'''

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()
for n in wf['nodes']:
    if n.get('name') == 'ValidarEmail':
        n['parameters']['jsCode'] = EMAIL_CODE
        print('ValidarEmail jsCode atualizado.')
        break

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT {r.status_code} updatedAt={r.json().get("updatedAt") if r.status_code<300 else r.text[:300]}')
