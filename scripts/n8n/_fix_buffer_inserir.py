"""
Fix do BufferInserir do workflow Vero.

Bug: a expressao JS do template do n8n usava chr(39) (funcao SQL/Python)
em vez de String.fromCharCode(39). chr nao existe em JS context — a
expressao inteira falha e vira string literal 'undefined' na query.

Resultado: todas as mensagens entravam no buffer com conteudo='undefined'.
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

NEW_QUERY = (
    "INSERT INTO vero_message_buffer (telefone, conteudo, tem_imagem, url_imagem) "
    "VALUES ("
    "'{{ $node['Entrada'].json.telefone }}', "
    "'{{ String($node['Entrada'].json.mensagem || '').split(\"'\").join(\"''\") }}', "
    "{{ $node['Entrada'].json.tem_imagem ? 'TRUE' : 'FALSE' }}, "
    "'{{ String($node['Entrada'].json.url_imagem || '').split(\"'\").join(\"''\") }}'"
    ") RETURNING id;"
)

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

found = False
for n in wf['nodes']:
    if n.get('name') == 'BufferInserir':
        antiga = n['parameters'].get('query', '')[:120]
        n['parameters']['query'] = NEW_QUERY
        print('BufferInserir query atualizada.')
        print(f'  ANTES: {antiga}...')
        print(f'  AGORA: {NEW_QUERY[:120]}...')
        found = True
        break

if not found:
    print('ERRO: nodo BufferInserir nao encontrado.')
    sys.exit(1)

allowed = {'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
           'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:400])
