# -*- coding: utf-8 -*-
"""
Adiciona ramo no workflow Vero pra registrar no Inbox as mensagens que um
humano envia DIRETO pelo WhatsApp (fromMe=true, mas NAO via API do bot).

Hoje o filtro 'Mensagem de Cliente?' joga fora todo fromMe=true. Esse ramo
intercepta o branch FALSE: se for fromMe=true E wasSentByApi!=true (humano
digitou no celular), registra como mensagem de Agente no Hubtrix.

Topologia nova:
  Mensagem de Cliente?[1 FALSE] -> Humano Digitou Direto? (IF)
     [true]  -> Registrar Msg Humano (HTTP) -> Respond Ignored
     [false] -> Respond Ignored
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
WF = 'Df1BgcXdg3HAUZwf'

r = requests.get(f'{BASE}/api/v1/workflows/{WF}', headers=HEADERS, timeout=15)
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'Registrar Msg Humano' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

# Credencial httpHeaderAuth do RegistrarMsgCliente (Hubtrix N8N Webhook)
cred = None
for n in wf['nodes']:
    if n['name'] == 'RegistrarMsgCliente':
        cred = (n.get('credentials') or {}).get('httpHeaderAuth')
        break
if not cred:
    print('ERRO: credencial Hubtrix N8N Webhook nao encontrada.')
    sys.exit(1)

# IF — humano digitou direto?  fromMe=true E wasSentByApi != true E tem texto
no_if = {
    'parameters': {
        'conditions': {
            'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
            'conditions': [
                {
                    'id': 'hd-1',
                    'leftValue': "={{ $json.body?.message?.fromMe === true }}",
                    'rightValue': '',
                    'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True},
                },
                {
                    'id': 'hd-2',
                    'leftValue': "={{ $json.body?.message?.wasSentByApi === true }}",
                    'rightValue': '',
                    'operator': {'type': 'boolean', 'operation': 'false', 'singleValue': True},
                },
                {
                    'id': 'hd-3',
                    'leftValue': "={{ !!($json.body?.message?.text) }}",
                    'rightValue': '',
                    'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True},
                },
            ],
            'combinator': 'and',
        },
        'looseTypeValidation': True,
        'options': {},
    },
    'type': 'n8n-nodes-base.if',
    'typeVersion': 2.2,
    'position': [-1780, 320],
    'id': 'humano-digitou-direto',
    'name': 'Humano Digitou Direto?',
}

# HTTP — registra a mensagem do humano no Hubtrix como remetente_tipo=agente
BODY = (
    '={\n'
    '  "tenant_slug":     "tr-carrion",\n'
    '  "telefone":        {{ JSON.stringify(String($json.body?.chat?.wa_chatid || $json.body?.chat?.phone || \'\').split(\'@\')[0]) }},\n'
    '  "conteudo":        {{ JSON.stringify($json.body?.message?.text || \'\') }},\n'
    '  "direcao":         "enviada",\n'
    '  "remetente_tipo":  "agente",\n'
    '  "canal_identif":   "553181167572"\n'
    '}'
)
no_http = {
    'parameters': {
        'method': 'POST',
        'url': 'https://app.hubtrix.com.br/api/public/n8n/inbox/mensagem/',
        'authentication': 'genericCredentialType',
        'genericAuthType': 'httpHeaderAuth',
        'sendHeaders': True,
        'headerParameters': {'parameters': [{'name': 'Content-Type', 'value': 'application/json'}]},
        'sendBody': True,
        'specifyBody': 'json',
        'jsonBody': BODY,
        'options': {'timeout': 10000, 'response': {'response': {'neverError': True}}},
    },
    'type': 'n8n-nodes-base.httpRequest',
    'typeVersion': 4.2,
    'position': [-1560, 240],
    'id': 'registrar-msg-humano',
    'name': 'Registrar Msg Humano',
    'credentials': {'httpHeaderAuth': cred},
}

wf['nodes'].append(no_if)
wf['nodes'].append(no_http)

conns = wf['connections']
# Mensagem de Cliente?[1 FALSE] passa a apontar pro IF novo
mc = conns.get('Mensagem de Cliente?', {}).get('main', [])
while len(mc) < 2:
    mc.append([])
mc[1] = [{'node': 'Humano Digitou Direto?', 'type': 'main', 'index': 0}]
conns['Mensagem de Cliente?'] = {'main': mc}

# IF: true -> Registrar Msg Humano | false -> Respond Ignored
conns['Humano Digitou Direto?'] = {'main': [
    [{'node': 'Registrar Msg Humano', 'type': 'main', 'index': 0}],
    [{'node': 'Respond Ignored', 'type': 'main', 'index': 0}],
]}
# Registrar Msg Humano -> Respond Ignored (encerra o webhook)
conns['Registrar Msg Humano'] = {'main': [[{'node': 'Respond Ignored', 'type': 'main', 'index': 0}]]}

print('Ramo adicionado:')
print('  Mensagem de Cliente?[FALSE] -> Humano Digitou Direto?')
print('    [true]  -> Registrar Msg Humano -> Respond Ignored')
print('    [false] -> Respond Ignored')

allowed = {'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
           'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
