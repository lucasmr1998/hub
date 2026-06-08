"""
Faz o nodo RegistrarMsgCliente espelhar TAMBEM os dados capturados pela
sessao do bot (nome, email, cpf, cep...) pro Hubtrix atualizar o Lead a
cada turno — em vez de so no Enviar Lead Hubtrix do final do fluxo.

O webhook /api/public/n8n/inbox/mensagem/ ja aceita 'dados_lead' e
'nome_contato' e atualiza apenas campos vazios (idempotente, nao
sobrescreve).
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

NEW_BODY = (
    '={\n'
    '  "tenant_slug":   "tr-carrion",\n'
    '  "telefone":      {{ JSON.stringify($node[\'Entrada\'].json.telefone) }},\n'
    '  "conteudo":      {{ JSON.stringify($node[\'Entrada\'].json.mensagem || \'(midia)\') }},\n'
    '  "direcao":       "recebida",\n'
    '  "canal_identif": "553181167572",\n'
    '  "tipo_conteudo": "{{ $node[\'Entrada\'].json.tem_imagem ? \'imagem\' : \'texto\' }}",\n'
    '  "arquivo_url":   {{ JSON.stringify($node[\'Entrada\'].json.url_imagem || \'\') }},\n'
    '  "nome_contato":  {{ JSON.stringify(($node[\'Load Session\'].json.dados && $node[\'Load Session\'].json.dados.nome) || \'\') }},\n'
    '  "dados_lead":    {{ JSON.stringify($node[\'Load Session\'].json.dados || {}) }}\n'
    '}'
)

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

found = False
for n in wf['nodes']:
    if n.get('name') == 'RegistrarMsgCliente':
        n['parameters']['jsonBody'] = NEW_BODY
        found = True
        print('RegistrarMsgCliente: body atualizado com dados_lead + nome_contato')
        break

if not found:
    print('ERRO: nodo nao encontrado')
    sys.exit(1)

allowed = {'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
           'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
