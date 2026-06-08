# -*- coding: utf-8 -*-
"""
Reformata a lista de planos pro estilo carinhoso pedido pela Kelle:

1️⃣ 550 Mega + Wi-Fi 6
\U0001f4b0 R$ 97,90 no PIX recorrente ou debito em conta
\U0001f4c4 R$ 107,90 no boleto

Atualiza GerarCatalogoPlanos e GerarCatalogoPlanos2 (mesmo codigo).
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

# Bloco JS novo que gera lista_formatada no estilo carinhoso
NOVO_BLOCO = (
    "const EMOJI_NUM = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣'];\n"
    "const lista_formatada = planos.length\n"
    "  ? '\U0001f4f6 *Planos disponiveis:*\\n\\n' + planos.map((p, i) => {\n"
    "      const num = EMOJI_NUM[i] || `${i+1}.`;\n"
    "      const pix = p.pix.toFixed(2).replace('.', ',');\n"
    "      const bol = p.boleto.toFixed(2).replace('.', ',');\n"
    "      return `${num} ${p.label}\\n` +\n"
    "             `\U0001f4b0 R$ ${pix} no PIX recorrente ou debito em conta\\n` +\n"
    "             `\U0001f4c4 R$ ${bol} no boleto`;\n"
    "    }).join('\\n\\n')\n"
    "  : '(catalogo nao disponivel pra essa regiao)';"
)

r = requests.get(f'{BASE}/api/v1/workflows/{WF}', headers=HEADERS, timeout=15)
wf = r.json()

mud = 0
for n in wf['nodes']:
    if n['name'] in ('GerarCatalogoPlanos', 'GerarCatalogoPlanos2'):
        code = n['parameters']['jsCode']
        ini = code.find('const lista_formatada =')
        fim = code.find(';', code.find("'(catalogo nao disponivel"))
        if ini == -1 or fim == -1:
            print(f'  {n["name"]}: nao achei o bloco — pulado')
            continue
        code = code[:ini] + NOVO_BLOCO + code[fim + 1:]
        n['parameters']['jsCode'] = code
        print(f'  {n["name"]}: lista_formatada reformatada')
        mud += 1

if not mud:
    print('Nada mudou.')
    sys.exit(1)

allowed = {'saveExecutionProgress', 'saveManualExecutions', 'saveDataErrorExecution',
           'saveDataSuccessExecution', 'executionTimeout', 'errorWorkflow', 'timezone', 'executionOrder'}
clean = {k: v for k, v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
