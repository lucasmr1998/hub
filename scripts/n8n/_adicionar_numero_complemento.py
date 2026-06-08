"""
Adiciona estados aguarda_numero e aguarda_complemento entre CEP e plano.

Antes:  aguarda_cep -> aguarda_plano
Depois: aguarda_cep -> aguarda_numero -> aguarda_complemento -> aguarda_plano

Nodos novos:
- Step Aguarda Numero (Set) — captura numero da residencia
- Step Aguarda Complemento (Set) — captura complemento (ou 'sem')

Atualizar Step Aguarda CEP:
- resposta_bot: ja NAO lista planos. Apenas confirma cobertura e pergunta numero.
- proximo_nodo: aguarda_numero
(A lista de planos passa pro Step Aguarda Complemento)

Atualizar Step Aguarda Complemento:
- resposta_bot: lista planos da cidade e pergunta qual.
- proximo_nodo: aguarda_plano
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

NODES_NEW = [
    # Step Aguarda Numero — depois do CEP, captura numero da residencia
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "san1", "name": "resposta_bot",
                     "value": "Tem algum complemento? (ex: apto 102, bloco B, fundos) Se nao tiver, manda 'nao'.",
                     "type": "string"},
                    {"id": "san2", "name": "proximo_nodo", "value": "aguarda_complemento", "type": "string"},
                    {"id": "san3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ numero: String($node['Entrada'].json.mensagem).trim() }) }}"),
                     "type": "object"},
                    {"id": "san4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-640, 1000],
        "id": "step-aguarda-numero",
        "name": "Step Aguarda Numero",
    },
    # Step Aguarda Complemento — captura complemento (ou nada) e apresenta planos
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sac1", "name": "resposta_bot",
                     "value": ("=Otimo! Em {{ $node['Load Session'].json.dados.cidade }} a Vero tem:\n\n"
                               "{{ $node['GerarCatalogoPlanos'].json.lista_formatada }}\n\n"
                               "Qual te chama mais? Pode mandar o numero ou descrever."),
                     "type": "string"},
                    {"id": "sac2", "name": "proximo_nodo", "value": "aguarda_plano", "type": "string"},
                    {"id": "sac3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ complemento: (() => { "
                               "  const m = String($node['Entrada'].json.mensagem).trim().toLowerCase(); "
                               "  if (['nao','não','n','nenhum','n tem','sem','-','.'].includes(m)) return ''; "
                               "  return $node['Entrada'].json.mensagem.trim(); "
                               "})() }) }}"),
                     "type": "object"},
                    {"id": "sac4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-640, 1200],
        "id": "step-aguarda-complemento",
        "name": "Step Aguarda Complemento",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'Step Aguarda Numero' in existing:
    print('Ja existe. Abortando (idempotencia).')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# 1. Atualizar Step Aguarda CEP — agora pergunta numero (nao mais lista planos)
for n in wf['nodes']:
    if n.get('name') == 'Step Aguarda CEP':
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'resposta_bot':
                a['value'] = ("=Perfeito! 😊 A Vero atende {{ $node['HTTP ViaCEP'].json.localidade }}/{{ $node['HTTP ViaCEP'].json.uf }}.\n\n"
                              "Qual o numero da sua casa?")
                print('Step Aguarda CEP: resposta agora pede numero da casa')
            elif a.get('name') == 'proximo_nodo':
                a['value'] = 'aguarda_numero'
                print('Step Aguarda CEP: proximo_nodo = aguarda_numero')
        break

# 2. Adicionar branches no Switch (Por Nodo Atual) pra aguarda_numero e aguarda_complemento
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
if switch_node:
    rules = switch_node['parameters']['rules']['values']
    existing_keys = {r.get('outputKey') for r in rules}
    for novo in ['aguarda_numero', 'aguarda_complemento']:
        if novo not in existing_keys:
            rules.append({
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                    "conditions": [{
                        "id": f"sw-{novo}",
                        "leftValue": "={{ $json.nodo_atual }}",
                        "rightValue": novo,
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                    "combinator": "and",
                },
                "renameOutput": True,
                "outputKey": novo,
            })
            print(f'Switch: adicionada rule {novo}')

# 3. Connections — adicionar saidas do Switch pros novos estados
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
# Verifica quantos outputs ja existem; vamos adicionar 2 (numero + complemento)
print(f'Switch outputs antes: {len(switch_outs)}')
while len(switch_outs) < len(switch_node['parameters']['rules']['values']):
    switch_outs.append([])

# Acha os indices novos
for i, rule in enumerate(switch_node['parameters']['rules']['values']):
    if rule.get('outputKey') == 'aguarda_numero':
        switch_outs[i] = [{'node': 'Step Aguarda Numero', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]={rule["outputKey"]} -> Step Aguarda Numero')
    elif rule.get('outputKey') == 'aguarda_complemento':
        switch_outs[i] = [{'node': 'Step Aguarda Complemento', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]={rule["outputKey"]} -> Step Aguarda Complemento')

# 4. Step Aguarda Numero -> Save Session
conns['Step Aguarda Numero'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Aguarda Complemento'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# PUT
allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code} updatedAt={r.json().get("updatedAt") if r.status_code<300 else r.text[:300]}')
print('\nFluxo agora: aguarda_cep -> aguarda_numero -> aguarda_complemento -> aguarda_plano (com lista)')
