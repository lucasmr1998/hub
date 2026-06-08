"""
Adiciona estado aguarda_confirmacao_cep entre aguarda_cep e aguarda_numero.

Antes: aguarda_cep -> aguarda_numero
Depois: aguarda_cep -> aguarda_confirmacao_cep -> (sim: aguarda_numero, nao: aguarda_cep)

Step Aguarda CEP MUDA:
- resposta_bot: mostra endereco completo "Achei: Rua X, Bairro Y, Cidade/UF. Esta correto?"
- proximo_nodo: aguarda_confirmacao_cep

Novos nodos:
- ClassificarConfirmacao (code): matcha sim/nao em pt-br
- Confirmou? (IF)
- Step Confirma Sim (Set): pergunta numero, vai pra aguarda_numero
- Step Confirma Nao (Set): pede CEP de novo, volta pra aguarda_cep
- Step Reasking Confirma (Set): se nao reconheceu sim/nao
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

CLASSIFICAR_CODE = '''// ClassificarConfirmacao — yes/no em pt-br
let raw = '';
try { raw = $('Entrada').first().json.mensagem || ''; } catch(e) {}
const m = String(raw).trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');

const SIMs = ['sim', 's', 'isso', 'isso ai', 'isso mesmo', 'esta certo', 'ta certo', 'confirmo', 'correto',
              'ok', 'okay', 'beleza', 'show', 'positivo', 'eh isso', 'aham', 'uhum', 'pode ser',
              'esta correto', 'ta correto', 'ta', 'yes', 'y', '👍'];
const NAOs = ['nao', 'n', 'errado', 'incorreto', 'esta errado', 'ta errado', 'negativo',
              'no', 'nope', 'nada', 'nao eh', 'nao mesmo', '👎'];

let resultado = 'unknown';
if (SIMs.some(w => m === w || m.startsWith(w + ' '))) resultado = 'sim';
else if (NAOs.some(w => m === w || m.startsWith(w + ' '))) resultado = 'nao';

return [{ json: { confirmacao: resultado, mensagem_norm: m } }];'''

NODES_NEW = [
    {
        "parameters": {"jsCode": CLASSIFICAR_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-640, 750],
        "id": "classificar-confirmacao",
        "name": "ClassificarConfirmacao",
    },
    {
        "parameters": {
            "rules": {
                "values": [
                    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                     "conditions": [{"id": "c-sim", "leftValue": "={{ $json.confirmacao }}", "rightValue": "sim",
                                     "operator": {"type": "string", "operation": "equals"}}],
                     "combinator": "and"}, "renameOutput": True, "outputKey": "sim"},
                    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                     "conditions": [{"id": "c-nao", "leftValue": "={{ $json.confirmacao }}", "rightValue": "nao",
                                     "operator": {"type": "string", "operation": "equals"}}],
                     "combinator": "and"}, "renameOutput": True, "outputKey": "nao"},
                ]
            },
            "looseTypeValidation": True,
            "options": {"fallbackOutput": "extra"},
        },
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [-400, 750],
        "id": "confirmou-switch",
        "name": "Confirmou?",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "scs1", "name": "resposta_bot",
                     "value": "Otimo! Qual o numero da sua casa?", "type": "string"},
                    {"id": "scs2", "name": "proximo_nodo", "value": "aguarda_numero", "type": "string"},
                    {"id": "scs3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "scs4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 700],
        "id": "step-confirma-sim",
        "name": "Step Confirma Sim",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "scn1", "name": "resposta_bot",
                     "value": "Ah ok, me manda o CEP correto entao?", "type": "string"},
                    {"id": "scn2", "name": "proximo_nodo", "value": "aguarda_cep", "type": "string"},
                    {"id": "scn3", "name": "novas_vars",
                     "value": ("={{ (() => { const d = Object.assign({}, $node['Load Session'].json.dados); "
                               "delete d.cep; delete d.cidade; delete d.estado; delete d.bairro; "
                               "return d; })() }}"),
                     "type": "object"},
                    {"id": "scn4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 800],
        "id": "step-confirma-nao",
        "name": "Step Confirma Nao",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "src1", "name": "resposta_bot",
                     "value": "Nao entendi 😅 Responde com 'sim' se o endereco esta correto ou 'nao' pra trocar o CEP.",
                     "type": "string"},
                    {"id": "src2", "name": "proximo_nodo", "value": "aguarda_confirmacao_cep", "type": "string"},
                    {"id": "src3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "src4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 900],
        "id": "step-reasking-confirma",
        "name": "Step Reasking Confirma",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'ClassificarConfirmacao' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Atualiza Step Aguarda CEP: agora mostra endereco + pede confirmacao
for n in wf['nodes']:
    if n.get('name') == 'Step Aguarda CEP':
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'resposta_bot':
                a['value'] = ("=Achei seu endereco:\n\n"
                              "📍 {{ $node['HTTP ViaCEP'].json.logradouro || '(sem logradouro)' }}\n"
                              "📍 {{ $node['HTTP ViaCEP'].json.bairro }} - {{ $node['HTTP ViaCEP'].json.localidade }}/{{ $node['HTTP ViaCEP'].json.uf }}\n\n"
                              "Esta correto? (sim/nao)")
                print('Step Aguarda CEP: agora pede confirmacao do endereco')
            elif a.get('name') == 'proximo_nodo':
                a['value'] = 'aguarda_confirmacao_cep'
                print('Step Aguarda CEP: proximo_nodo = aguarda_confirmacao_cep')
        break

# Switch — adicionar rule aguarda_confirmacao_cep
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
rules = switch_node['parameters']['rules']['values']
keys = {r.get('outputKey') for r in rules}
if 'aguarda_confirmacao_cep' not in keys:
    rules.append({
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "sw-confirma",
                "leftValue": "={{ $json.nodo_atual }}",
                "rightValue": "aguarda_confirmacao_cep",
                "operator": {"type": "string", "operation": "equals"},
            }],
            "combinator": "and",
        },
        "renameOutput": True,
        "outputKey": "aguarda_confirmacao_cep",
    })
    print('Switch: adicionada rule aguarda_confirmacao_cep')

# Connections — Switch[aguarda_confirmacao_cep] -> ClassificarConfirmacao -> Confirmou? -> Step Confirma X
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
while len(switch_outs) < len(rules):
    switch_outs.append([])
for i, rule in enumerate(rules):
    if rule.get('outputKey') == 'aguarda_confirmacao_cep':
        switch_outs[i] = [{'node': 'ClassificarConfirmacao', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]=aguarda_confirmacao_cep -> ClassificarConfirmacao')

conns['ClassificarConfirmacao'] = {'main': [[{'node': 'Confirmou?', 'type': 'main', 'index': 0}]]}
conns['Confirmou?'] = {
    'main': [
        [{'node': 'Step Confirma Sim', 'type': 'main', 'index': 0}],            # sim
        [{'node': 'Step Confirma Nao', 'type': 'main', 'index': 0}],            # nao
        [{'node': 'Step Reasking Confirma', 'type': 'main', 'index': 0}],       # fallback
    ]
}
conns['Step Confirma Sim'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Confirma Nao'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking Confirma'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
print('\nNovo fluxo: CEP -> mostra endereco -> aguarda_confirmacao_cep -> (sim: numero, nao: novo CEP)')
