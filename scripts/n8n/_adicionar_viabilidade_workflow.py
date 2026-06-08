"""
Adiciona checagem de cobertura via API Hubtrix no workflow Vero,
depois do CEP Existe? = true e antes do Step Aguarda CEP.

Topologia nova:
  ... HTTP ViaCEP -> CEP Existe? (true)
                       -> HTTP Hubtrix Viabilidade
                           -> Atendido?
                               true  -> Step Aguarda CEP
                               false -> Step Reasking CEP SemCobertura -> Save Session
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
CRED_ID = 'ix3a5mNnIdesAZRz'  # Hubtrix N8N Webhook (mesmo do lead)
CRED_NAME = 'Hubtrix N8N Webhook'

NODES_NEW = [
    {
        "parameters": {
            "method": "POST",
            "url": "https://app.hubtrix.com.br/api/public/n8n/viabilidade/",
            "authentication": "genericCredentialType",
            "genericAuthType": "httpHeaderAuth",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {"name": "Content-Type", "value": "application/json"}
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": ("={\n"
                         "  \"tenant_slug\": \"tr-carrion\",\n"
                         "  \"cidade\": \"{{ $node['HTTP ViaCEP'].json.localidade }}\",\n"
                         "  \"estado\": \"{{ $node['HTTP ViaCEP'].json.uf }}\",\n"
                         "  \"cep\": \"{{ $node['ValidarCepFormato'].json.cep_limpo }}\"\n"
                         "}"),
            "options": {"timeout": 5000},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [440, -350],
        "id": "http-viabilidade",
        "name": "HTTP Hubtrix Viabilidade",
        "credentials": {
            "httpHeaderAuth": {"id": CRED_ID, "name": CRED_NAME}
        },
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [
                    {
                        "id": "at-1",
                        "leftValue": "={{ $json.atendido }}",
                        "rightValue": "",
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }
                ],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [620, -350],
        "id": "atendido",
        "name": "Atendido?",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "rsc1", "name": "resposta_bot",
                     "value": "=Infelizmente ainda nao atendemos {{ $node['HTTP ViaCEP'].json.localidade }}/{{ $node['HTTP ViaCEP'].json.uf }}. Quer entrar na lista de espera? Manda outro CEP de uma regiao atendida pra continuar.",
                     "type": "string"},
                    {"id": "rsc2", "name": "proximo_nodo", "value": "aguarda_cep", "type": "string"},
                    {"id": "rsc3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "rsc4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [800, -400],
        "id": "step-reasking-cep-sem-cobertura",
        "name": "Step Reasking CEP SemCobertura",
    },
]

# GET workflow
r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'HTTP Hubtrix Viabilidade' in existing:
    print('HTTP Hubtrix Viabilidade ja existe. Abortando (idempotencia).')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Reescreve connections:
# Antes:  CEP Existe? true -> Step Aguarda CEP
# Depois: CEP Existe? true -> HTTP Hubtrix Viabilidade -> Atendido?
#                                                          true  -> Step Aguarda CEP
#                                                          false -> Step Reasking CEP SemCobertura -> Save Session
conns = wf['connections']
conns['CEP Existe?']['main'][0] = [{'node': 'HTTP Hubtrix Viabilidade', 'type': 'main', 'index': 0}]
conns['HTTP Hubtrix Viabilidade'] = {'main': [[{'node': 'Atendido?', 'type': 'main', 'index': 0}]]}
conns['Atendido?'] = {
    'main': [
        [{'node': 'Step Aguarda CEP', 'type': 'main', 'index': 0}],                  # true
        [{'node': 'Step Reasking CEP SemCobertura', 'type': 'main', 'index': 0}],   # false
    ]
}
conns['Step Reasking CEP SemCobertura'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# PUT
allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT status: {r.status_code}')
if r.status_code >= 300:
    print(f'BODY: {r.text[:1500]}')
    raise SystemExit(1)
print(f'updatedAt: {r.json().get("updatedAt")}')
print('\nAdicionados: HTTP Hubtrix Viabilidade + Atendido? + Step Reasking CEP SemCobertura')
print('\nIMPORTANTE: o endpoint /api/public/n8n/viabilidade/ so funciona apos Rebuild do Hubtrix em prod.')
