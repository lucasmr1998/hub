"""
Fix: 'Consultar Hubtrix Estado' (HTTP) substitui o $json com seu response,
quebrando DetectarReset/DetectarPedidoHumano/Por Nodo Atual que esperam
{telefone, nodo_atual, dados} do Load Session.

Solucao: inserir nodo Code 'Merge Hubtrix Estado' entre Consultar Hubtrix
Estado e DetectarReset que reconstrói o objeto do Load Session + adiciona
'hubtrix_modo' como campo extra. O IF 'Ja em Humano?' continua lendo
$node['Consultar Hubtrix Estado'] (esse caminho ja eh by-name, nao depende
do flow $json).
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

MERGE_CODE = '''// Preserva o output do Load Session no flow data
// HTTP node antes deste substituiu o $json — recupera do node por nome.
const ls = $node['Load Session'].json;
const hub = $input.first().json;  // output do Consultar Hubtrix Estado

return [{ json: {
  telefone:    ls.telefone,
  nodo_atual:  ls.nodo_atual,
  dados:       ls.dados || {},
  // extras pra IF/regras consultarem
  hubtrix_modo:     hub.modo_atendimento || null,
  hubtrix_existe:   hub.existe || false,
  hubtrix_agente:   hub.agente_id || null,
}}];'''

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'Merge Hubtrix Estado' in existing:
    print('Ja existe Merge Hubtrix Estado. Abortando.')
    sys.exit(0)

novo_nodo = {
    'parameters': {'jsCode': MERGE_CODE},
    'type': 'n8n-nodes-base.code',
    'typeVersion': 2,
    'position': [-450, 0],
    'id': 'merge-hubtrix-estado',
    'name': 'Merge Hubtrix Estado',
}
wf['nodes'].append(novo_nodo)

# Reposiciona conexao: Consultar Hubtrix Estado -> Merge -> DetectarReset
conns = wf['connections']
conns['Consultar Hubtrix Estado'] = {'main': [[{'node': 'Merge Hubtrix Estado', 'type': 'main', 'index': 0}]]}
conns['Merge Hubtrix Estado']     = {'main': [[{'node': 'DetectarReset',        'type': 'main', 'index': 0}]]}
print('Conexoes: Consultar Hubtrix Estado -> Merge Hubtrix Estado -> DetectarReset')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
