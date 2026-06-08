"""
Adiciona check Hubtrix: se operador assumiu a conversa no Inbox
(Conversa.modo_atendimento='humano'), o bot fica em silencio.

Mudancas:
1. Novo nodo 'Consultar Hubtrix Estado' (HTTP GET /api/public/n8n/conversa/estado/)
   inserido entre Load Session e DetectarReset.
2. Estende o IF 'Ja em Humano?' (combinator=and):
   - cond1: Load Session.nodo_atual notEquals 'aguarda_humano'
   - cond2 (nova): Consultar Hubtrix Estado.modo_atendimento notEquals 'humano'
   Se qualquer um cair em humano, vai pra Respond Humano Silencioso.

Idempotente. So pula se 'Consultar Hubtrix Estado' ja existir.
"""
import json
import sys
import io
import requests
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env_n8n = dotenv_values('.env.n8n')
BASE = env_n8n['N8N_BASE_URL'].rstrip('/')
KEY = env_n8n['N8N_API_KEY']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}
WF_ID = 'Df1BgcXdg3HAUZwf'

# Lemos o N8N_WEBHOOK_SECRET de .env.n8n_webhook (mesmo arquivo dos outros scripts)
# Se nao tiver, o ConsultarHubtrixEstado falha auth. Tenta varias fontes.
WEBHOOK_SECRET = (
    env_n8n.get('N8N_WEBHOOK_SECRET')
    or dotenv_values('.env').get('N8N_WEBHOOK_SECRET')
    or ''
)
if not WEBHOOK_SECRET:
    print('AVISO: N8N_WEBHOOK_SECRET nao encontrado nos .env locais.')
    print('       O credencial httpHeaderAuth do n8n ja deve ter o secret configurado.')

# Le credencial httpHeaderAuth ja existente no workflow pra reutilizar
r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

# Pega credencial do Enviar Lead Hubtrix pra herdar
cred_auth = None
for n in wf['nodes']:
    if n.get('name') == 'Enviar Lead Hubtrix':
        cred_auth = (n.get('credentials') or {}).get('httpHeaderAuth')
        break
if not cred_auth:
    print('ERRO: credencial httpHeaderAuth do Enviar Lead Hubtrix nao encontrada.')
    sys.exit(1)

existing = {n['name'] for n in wf['nodes']}
if 'Consultar Hubtrix Estado' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

# 1. Novo nodo HTTP GET — consulta estado da conversa no Hubtrix
novo_nodo = {
    'parameters': {
        'method': 'GET',
        'url': 'https://app.hubtrix.com.br/api/public/n8n/conversa/estado/',
        'authentication': 'genericCredentialType',
        'genericAuthType': 'httpHeaderAuth',
        'sendQuery': True,
        'queryParameters': {
            'parameters': [
                {'name': 'tenant_slug', 'value': 'tr-carrion'},
                {'name': 'telefone', 'value': "={{ $node['Entrada'].json.telefone }}"},
            ]
        },
        'options': {
            'response': {'response': {'neverError': True}},
            'timeout': 8000,
        },
    },
    'type': 'n8n-nodes-base.httpRequest',
    'typeVersion': 4.2,
    'position': [-500, 0],
    'id': 'consultar-hubtrix-estado',
    'name': 'Consultar Hubtrix Estado',
    'credentials': {'httpHeaderAuth': cred_auth},
}
wf['nodes'].append(novo_nodo)
print('Nodo Consultar Hubtrix Estado adicionado.')

# 2. Reposicionar Load Session -> Consultar Hubtrix Estado -> DetectarReset
conns = wf['connections']
conns['Load Session'] = {'main': [[{'node': 'Consultar Hubtrix Estado', 'type': 'main', 'index': 0}]]}
conns['Consultar Hubtrix Estado'] = {'main': [[{'node': 'DetectarReset', 'type': 'main', 'index': 0}]]}
print('Conexoes: Load Session -> Consultar Hubtrix Estado -> DetectarReset')

# 3. Estender o IF 'Ja em Humano?' — adiciona cond2 hubtrix.modo notEquals 'humano' (combinator=and)
for n in wf['nodes']:
    if n.get('name') == 'Ja em Humano?':
        conds = n['parameters']['conditions']['conditions']
        # Verifica se ja tem a check do Hubtrix
        if not any(c.get('id') == 'jeh-2-hubtrix' for c in conds):
            conds.append({
                'id': 'jeh-2-hubtrix',
                'leftValue': "={{ $node['Consultar Hubtrix Estado'].json.modo_atendimento }}",
                'rightValue': 'humano',
                'operator': {'type': 'string', 'operation': 'notEquals'},
            })
            n['parameters']['conditions']['combinator'] = 'and'
            print('IF Ja em Humano?: agora tambem checa Hubtrix.modo_atendimento')
        break

allowed = {'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
           'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
else:
    print('\nFeito:')
    print('  Load Session -> Consultar Hubtrix Estado -> DetectarReset -> DetectarPedidoHumano -> Ja em Humano?')
    print('  Se Hubtrix.modo=humano OU vero_session.nodo_atual=aguarda_humano: silencia bot.')
