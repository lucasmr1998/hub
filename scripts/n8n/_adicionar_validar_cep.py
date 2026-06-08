"""
Adiciona validacao de CEP no workflow Vero:
1. ValidarCepFormato (code) — regex 5+3 digitos, normaliza pra "00000000"
2. HTTP ViaCEP — consulta viacep.com.br/ws/{cep}/json
3. IF Formato CEP OK? — branch true/false
4. IF CEP Existe? — branch true/false (ViaCEP retorna {erro:true} se nao existe)
5. Step Reasking CEP Formato — mantem aguarda_cep, msg sobre formato
6. Step Reasking CEP NaoExiste — mantem aguarda_cep, msg sobre nao encontrado
7. Atualiza Step Aguarda CEP pra salvar cidade/estado/bairro vindo do ViaCEP

Topologia:
  Por Nodo Atual [aguarda_cep] -> ValidarCepFormato
                                     -> IF Formato OK?
                                          true  -> HTTP ViaCEP
                                                    -> IF CEP Existe?
                                                         true  -> Step Aguarda CEP (enriquecido)
                                                         false -> Step Reasking CEP NaoExiste
                                          false -> Step Reasking CEP Formato
  Steps Reasking -> Save Session
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

CEP_FORMATO_CODE = '''// ValidarCepFormato — regex 5+3 digitos, normaliza
const raw = $('Entrada').first().json.mensagem;
const limpo = raw ? String(raw).replace(/\\D/g, '') : '';
const valido = /^\\d{8}$/.test(limpo);
return [{
  json: {
    cep_input: raw,
    cep_limpo: limpo,
    formato_cep_valido: valido,
  }
}];'''

NODES_NEW = [
    {
        "parameters": {"jsCode": CEP_FORMATO_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-280, -300],
        "id": "validar-cep-formato",
        "name": "ValidarCepFormato",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [
                    {
                        "id": "fc-1",
                        "leftValue": "={{ $json.formato_cep_valido }}",
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
        "position": [-100, -300],
        "id": "formato-cep-ok",
        "name": "Formato CEP OK?",
    },
    {
        "parameters": {
            "method": "GET",
            "url": "=https://viacep.com.br/ws/{{ $json.cep_limpo }}/json/",
            "options": {"timeout": 5000},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [80, -350],
        "id": "viacep",
        "name": "HTTP ViaCEP",
        "continueOnFail": True,
        "onError": "continueRegularOutput",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [
                    {
                        "id": "ce-1",
                        "leftValue": "={{ $json.erro === true }}",
                        "rightValue": "",
                        "operator": {"type": "boolean", "operation": "false", "singleValue": True},
                    },
                    {
                        "id": "ce-2",
                        "leftValue": "={{ $json.localidade }}",
                        "rightValue": "",
                        "operator": {"type": "string", "operation": "exists", "singleValue": True},
                    }
                ],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [260, -350],
        "id": "cep-existe",
        "name": "CEP Existe?",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "rcf1", "name": "resposta_bot",
                     "value": "Hmm, esse CEP nao parece valido. Pode mandar de novo no formato 00000-000?",
                     "type": "string"},
                    {"id": "rcf2", "name": "proximo_nodo", "value": "aguarda_cep", "type": "string"},
                    {"id": "rcf3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "rcf4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [80, -200],
        "id": "step-reasking-cep-formato",
        "name": "Step Reasking CEP Formato",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "rcn1", "name": "resposta_bot",
                     "value": "Nao consegui encontrar esse CEP. Pode conferir?",
                     "type": "string"},
                    {"id": "rcn2", "name": "proximo_nodo", "value": "aguarda_cep", "type": "string"},
                    {"id": "rcn3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "rcn4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [440, -250],
        "id": "step-reasking-cep-naoexiste",
        "name": "Step Reasking CEP NaoExiste",
    },
]

# GET workflow
r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'ValidarCepFormato' in existing:
    print('ValidarCepFormato ja existe. Abortando (idempotencia).')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Atualizar Step Aguarda CEP pra salvar cidade/estado/bairro do ViaCEP
for n in wf['nodes']:
    if n.get('name') == 'Step Aguarda CEP':
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'novas_vars':
                # Enriquece com cidade/estado/bairro do ViaCEP
                a['value'] = ("={{ Object.assign({}, $node['Load Session'].json.dados, { "
                              "cep: $node['ValidarCepFormato'].json.cep_limpo, "
                              "cidade: $node['HTTP ViaCEP'].json.localidade, "
                              "estado: $node['HTTP ViaCEP'].json.uf, "
                              "bairro: $node['HTTP ViaCEP'].json.bairro }) }}")
                print('Step Aguarda CEP novas_vars atualizado (cidade/estado/bairro)')
                break
        break

# Connections
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])

# Acha output que aponta pra Step Aguarda CEP
out_idx_cep = None
for i, outs in enumerate(switch_outs):
    for tgt in (outs or []):
        if tgt.get('node') == 'Step Aguarda CEP':
            out_idx_cep = i
            break
    if out_idx_cep is not None:
        break
print(f'Output do Switch que vai pra Step Aguarda CEP: index={out_idx_cep}')
if out_idx_cep is None:
    raise SystemExit('Nao achei conexao Switch -> Step Aguarda CEP')

# Reescreve o output do Switch pra ir pro ValidarCepFormato
switch_outs[out_idx_cep] = [{'node': 'ValidarCepFormato', 'type': 'main', 'index': 0}]

conns['ValidarCepFormato'] = {'main': [[{'node': 'Formato CEP OK?', 'type': 'main', 'index': 0}]]}
conns['Formato CEP OK?'] = {
    'main': [
        [{'node': 'HTTP ViaCEP', 'type': 'main', 'index': 0}],            # true
        [{'node': 'Step Reasking CEP Formato', 'type': 'main', 'index': 0}],  # false
    ]
}
conns['HTTP ViaCEP'] = {'main': [[{'node': 'CEP Existe?', 'type': 'main', 'index': 0}]]}
conns['CEP Existe?'] = {
    'main': [
        [{'node': 'Step Aguarda CEP', 'type': 'main', 'index': 0}],            # true
        [{'node': 'Step Reasking CEP NaoExiste', 'type': 'main', 'index': 0}], # false
    ]
}
conns['Step Reasking CEP Formato'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking CEP NaoExiste'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# PUT
allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT status: {r.status_code}')
if r.status_code >= 300:
    print(f'BODY: {r.text[:1500]}')
    raise SystemExit(1)
print(f'updatedAt: {r.json().get("updatedAt")}')
print(f'\nNodos adicionados: ValidarCepFormato + Formato CEP OK? + HTTP ViaCEP + CEP Existe? + 2 Steps Reasking')
