"""
Adiciona chamada ao Hubtrix após cada imagem de RG validada.

Após "Step Aguarda RG Frente" (imagem ok) → POST /api/public/n8n/lead/imagem/ com RG frente
Após "Step Aguarda RG Verso"  (imagem ok) → POST /api/public/n8n/lead/imagem/ com RG verso

O endpoint Hubtrix cria ImagemLeadProspecto, o signal dispara e a automação do pipeline cria a Venda.
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
HUBTRIX_URL = env.get('HUBTRIX_URL', 'https://app.hubtrix.com.br').rstrip('/')
WEBHOOK_SECRET = env.get('HUBTRIX_N8N_WEBHOOK_SECRET', '')
TENANT_SLUG = 'tr-carrion'
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}
WF_ID = 'Df1BgcXdg3HAUZwf'

ENDPOINT = f'{HUBTRIX_URL}/api/public/n8n/lead/imagem/'

def fazer_node_registrar_imagem(node_id, node_name, descricao, url_var_expr, lead_id_expr):
    """Cria um node HTTP Request que registra a imagem no Hubtrix."""
    return {
        "parameters": {
            "method": "POST",
            "url": ENDPOINT,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "X-N8N-Webhook-Secret", "value": WEBHOOK_SECRET},
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                f'={{ {{ "tenant_slug": "{TENANT_SLUG}", '
                f'"lead_id": {lead_id_expr}, '
                f'"link_url": {url_var_expr}, '
                f'"descricao": "{descricao}" }} }}'
            ),
            "options": {"response": {"response": {"responseFormat": "json"}}},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [80, 2050 if 'Frente' in node_name else 2350],
        "id": node_id,
        "name": node_name,
        "continueOnFail": True,
    }


r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing_names = {n['name'] for n in wf['nodes']}
if 'Registrar RG Frente Hubtrix' in existing_names:
    print('Nodes ja existem. Abortando.')
    sys.exit(0)

# Pegar lead_id da sessao — disponivel como dado do step anterior
LEAD_ID_EXPR = "={{ $node['Load Session'].json.dados?.lead_id ?? $node['Load Session'].json.lead_id }}"
URL_FRENTE_EXPR = "={{ $node['ValidarImagemRGFrente'].json.url_imagem }}"
URL_VERSO_EXPR = "={{ $node['ValidarImagemRGVerso'].json.url_imagem }}"

node_frente = fazer_node_registrar_imagem(
    'registrar-rg-frente-hubtrix',
    'Registrar RG Frente Hubtrix',
    'RG frente',
    URL_FRENTE_EXPR,
    LEAD_ID_EXPR,
)
node_verso = fazer_node_registrar_imagem(
    'registrar-rg-verso-hubtrix',
    'Registrar RG Verso Hubtrix',
    'RG verso',
    URL_VERSO_EXPR,
    LEAD_ID_EXPR,
)

wf['nodes'].extend([node_frente, node_verso])

conns = wf['connections']

# Step Aguarda RG Frente -> Registrar RG Frente Hubtrix -> Save Session
# Atualmente: Step Aguarda RG Frente -> Save Session
conn_frente = conns.get('Step Aguarda RG Frente', {}).get('main', [[]])
destino_atual_frente = conn_frente[0] if conn_frente else []

conns['Step Aguarda RG Frente'] = {
    'main': [[{'node': 'Registrar RG Frente Hubtrix', 'type': 'main', 'index': 0}]]
}
conns['Registrar RG Frente Hubtrix'] = {
    'main': [destino_atual_frente]
}
print(f'Step Aguarda RG Frente -> Registrar RG Frente Hubtrix -> {[n.get("node") for n in destino_atual_frente]}')

# Step Aguarda RG Verso -> Registrar RG Verso Hubtrix -> Save Session
conn_verso = conns.get('Step Aguarda RG Verso', {}).get('main', [[]])
destino_atual_verso = conn_verso[0] if conn_verso else []

conns['Step Aguarda RG Verso'] = {
    'main': [[{'node': 'Registrar RG Verso Hubtrix', 'type': 'main', 'index': 0}]]
}
conns['Registrar RG Verso Hubtrix'] = {
    'main': [destino_atual_verso]
}
print(f'Step Aguarda RG Verso -> Registrar RG Verso Hubtrix -> {[n.get("node") for n in destino_atual_verso]}')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}

r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code == 200:
    print('OK — workflow atualizado.')
    print(f'Endpoint: POST {ENDPOINT}')
else:
    print(r.text[:300])
