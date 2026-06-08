"""
Adiciona estados aguarda_doc_rg_frente e aguarda_doc_rg_verso ENTRE email e confirmacao_final.

Fluxo:
  email -> aguarda_doc_rg_frente -> aguarda_doc_rg_verso -> aguarda_confirmacao_final

Detecta imagem no webhook do Uazapi:
- body.message.mediaType === 'image' OR body.mediaType === 'image' OR body.message.imageMessage
- URL: body.message.url OR body.message.imageUrl OR body.media.url

Adiciona ao Entrada: tem_imagem, url_imagem (extras)
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

# Expression que detecta se tem imagem
TEM_IMAGEM_EXPR = ("={{ (() => { "
                   "const b = $json.body || $json; "
                   "const mt = (b.message?.mediaType || b.mediaType || b.message?.messageType || '').toLowerCase(); "
                   "return mt.includes('image') || mt.includes('imagem') || !!(b.message?.imageMessage) || !!(b.message?.image) || !!(b.media); "
                   "})() }}")

URL_IMAGEM_EXPR = ("={{ (() => { "
                   "const b = $json.body || $json; "
                   "return b.message?.url || b.message?.imageUrl || b.message?.image?.url || b.media?.url || b.url || b.imageUrl || ''; "
                   "})() }}")

VALIDAR_IMAGEM_CODE = '''// ValidarImagem — checa se a entrada e imagem
let tem_imagem = false;
let url = '';
try { tem_imagem = $('Entrada').first().json.tem_imagem === true; } catch(e) {}
try { url = $('Entrada').first().json.url_imagem || ''; } catch(e) {}
return [{ json: {
  camada1_ok: tem_imagem && !!url,
  url_imagem: url,
}}];'''

NODES_NEW = [
    # ValidarImagem (reuso pra ambos estados, code identico funciona)
    {
        "parameters": {"jsCode": VALIDAR_IMAGEM_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-640, 2100],
        "id": "validar-imagem-rg-frente",
        "name": "ValidarImagemRGFrente",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "img-f-ok",
                    "leftValue": "={{ $json.camada1_ok }}",
                    "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                }],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [-400, 2100],
        "id": "imagem-frente-ok",
        "name": "Imagem RG Frente OK?",
    },
    # Step Aguarda RG Frente (Set) — pos validacao
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sarf1", "name": "resposta_bot",
                     "value": "Otimo, recebi a frente! 📸\n\nAgora manda uma foto do *verso* do RG, por favor.",
                     "type": "string"},
                    {"id": "sarf2", "name": "proximo_nodo", "value": "aguarda_doc_rg_verso", "type": "string"},
                    {"id": "sarf3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ doc_rg_frente_url: $node['ValidarImagemRGFrente'].json.url_imagem }) }}"),
                     "type": "object"},
                    {"id": "sarf4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 2050],
        "id": "step-aguarda-rg-frente",
        "name": "Step Aguarda RG Frente",
    },
    # Step Reasking RG Frente
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "srrf1", "name": "resposta_bot",
                     "value": "Preciso de uma *foto* da frente do seu RG (ou CNH). Pode mandar pelo WhatsApp como imagem?",
                     "type": "string"},
                    {"id": "srrf2", "name": "proximo_nodo", "value": "aguarda_doc_rg_frente", "type": "string"},
                    {"id": "srrf3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "srrf4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 2150],
        "id": "step-reasking-rg-frente",
        "name": "Step Reasking RG Frente",
    },

    # ValidarImagemRGVerso (separado pra clareza)
    {
        "parameters": {"jsCode": VALIDAR_IMAGEM_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-640, 2400],
        "id": "validar-imagem-rg-verso",
        "name": "ValidarImagemRGVerso",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "img-v-ok",
                    "leftValue": "={{ $json.camada1_ok }}",
                    "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                }],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [-400, 2400],
        "id": "imagem-verso-ok",
        "name": "Imagem RG Verso OK?",
    },
    # Step Aguarda RG Verso — pos validacao
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sarv1", "name": "resposta_bot",
                     "value": "Recebi o verso! ✅ Tudo certo com documentos.",
                     "type": "string"},
                    {"id": "sarv2", "name": "proximo_nodo", "value": "aguarda_confirmacao_final", "type": "string"},
                    {"id": "sarv3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ doc_rg_verso_url: $node['ValidarImagemRGVerso'].json.url_imagem }) }}"),
                     "type": "object"},
                    {"id": "sarv4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 2350],
        "id": "step-aguarda-rg-verso",
        "name": "Step Aguarda RG Verso",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "srrv1", "name": "resposta_bot",
                     "value": "Preciso de uma *foto* do verso do RG (ou CNH). Pode mandar como imagem?",
                     "type": "string"},
                    {"id": "srrv2", "name": "proximo_nodo", "value": "aguarda_doc_rg_verso", "type": "string"},
                    {"id": "srrv3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "srrv4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 2450],
        "id": "step-reasking-rg-verso",
        "name": "Step Reasking RG Verso",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'ValidarImagemRGFrente' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# 1. Atualizar Entrada — adicionar tem_imagem e url_imagem
for n in wf['nodes']:
    if n.get('name') == 'Entrada':
        # Mantem telefone e mensagem existentes, adiciona campos novos
        ass = n['parameters']['assignments']['assignments']
        # Adiciona se nao tiver
        names = {a['name'] for a in ass}
        if 'tem_imagem' not in names:
            ass.append({"id": "a3", "name": "tem_imagem", "value": TEM_IMAGEM_EXPR, "type": "boolean"})
        if 'url_imagem' not in names:
            ass.append({"id": "a4", "name": "url_imagem", "value": URL_IMAGEM_EXPR, "type": "string"})
        print('Entrada: adicionados tem_imagem + url_imagem')
        break

# 2. Step Aguarda Email (Final) e (via IA) MUDAM proximo_nodo de aguarda_confirmacao_final pra aguarda_doc_rg_frente
for n in wf['nodes']:
    if n.get('name') in ('Step Aguarda Email (Final)', 'Step Aguarda Email (via IA)'):
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'proximo_nodo':
                a['value'] = 'aguarda_doc_rg_frente'
            elif a.get('name') == 'resposta_bot':
                # Substitui o resumo (que ia pra confirmacao_final) por pedido de foto
                a['value'] = "Quase pronto! Pra fechar, manda uma *foto da frente* do seu RG (ou CNH) pelo WhatsApp."
        print(f'{n["name"]}: proximo_nodo=aguarda_doc_rg_frente, pede foto RG frente')

# 3. Switch — adicionar rules
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
rules = switch_node['parameters']['rules']['values']
keys = {r.get('outputKey') for r in rules}
for novo in ['aguarda_doc_rg_frente', 'aguarda_doc_rg_verso']:
    if novo not in keys:
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

# 4. Connections
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
while len(switch_outs) < len(rules):
    switch_outs.append([])
for i, rule in enumerate(rules):
    if rule.get('outputKey') == 'aguarda_doc_rg_frente':
        switch_outs[i] = [{'node': 'ValidarImagemRGFrente', 'type': 'main', 'index': 0}]
    elif rule.get('outputKey') == 'aguarda_doc_rg_verso':
        switch_outs[i] = [{'node': 'ValidarImagemRGVerso', 'type': 'main', 'index': 0}]

conns['ValidarImagemRGFrente'] = {'main': [[{'node': 'Imagem RG Frente OK?', 'type': 'main', 'index': 0}]]}
conns['Imagem RG Frente OK?'] = {
    'main': [
        [{'node': 'Step Aguarda RG Frente', 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking RG Frente', 'type': 'main', 'index': 0}],
    ]
}
conns['Step Aguarda RG Frente'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking RG Frente'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

conns['ValidarImagemRGVerso'] = {'main': [[{'node': 'Imagem RG Verso OK?', 'type': 'main', 'index': 0}]]}
conns['Imagem RG Verso OK?'] = {
    'main': [
        [{'node': 'Step Aguarda RG Verso', 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking RG Verso', 'type': 'main', 'index': 0}],
    ]
}
conns['Step Aguarda RG Verso'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking RG Verso'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# 5. PegarRespostaBot — adicionar novos Steps na lista
for n in wf['nodes']:
    if n.get('name') == 'PegarRespostaBot':
        code = n['parameters']['jsCode']
        new_entries = "'Step Aguarda RG Frente', 'Step Reasking RG Frente', 'Step Aguarda RG Verso', 'Step Reasking RG Verso',"
        if 'Step Aguarda RG Frente' not in code:
            # Insere antes da linha 'Step Aguarda Email (Final)'
            code = code.replace("'Step Aguarda Email (Final)'", new_entries + "\n  'Step Aguarda Email (Final)'")
            n['parameters']['jsCode'] = code
            print('PegarRespostaBot: incluidos Steps de RG')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
print('\nNovo fluxo: ... email -> aguarda_doc_rg_frente -> aguarda_doc_rg_verso -> aguarda_confirmacao_final')
