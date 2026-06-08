"""
Corrige bugs encontrados no teste exaustivo:
- #21: Nome vazio/curto/lixo eh aceito -> adicionar validacao + reasking
- #20: Nome de 500 chars salvo inteiro -> truncar pra 150
"""
import json, sys, io, requests
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}
WF_ID = 'Df1BgcXdg3HAUZwf'

VALIDAR_NOME_CODE = '''// ValidarNome — rejeita vazio/curto/sem letras/lixo
let raw = '';
try { raw = $('Entrada').first().json.mensagem || ''; } catch(e) {}
const trimmed = String(raw).trim();

// Regras:
// 1. Minimo 2 caracteres
// 2. Pelo menos 50% das letras (filtra "asdfgh" e numeros)
// 3. Max 150 caracteres (trunca)
// 4. Deve ter pelo menos 1 letra
let valido = trimmed.length >= 2 && trimmed.length <= 150;
if (valido) {
  const letras = (trimmed.match(/[a-zA-ZáéíóúâêîôûãõàèìòùçÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇñÑ]/g) || []).length;
  const total = trimmed.replace(/\\s/g, '').length;
  valido = letras >= 2 && (total === 0 || letras / total >= 0.5);
}

// Capitalizar primeira letra de cada palavra (cosmetic)
const formatted = valido ? trimmed.split(/\\s+/).map(w =>
  w.length > 0 ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w
).join(' ').slice(0, 150) : trimmed;

return [{ json: {
  nome_input: raw,
  nome_formatado: formatted,
  nome_valido: valido,
}}];'''

NODES_NEW = [
    {
        "parameters": {"jsCode": VALIDAR_NOME_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [450, 250],   # Y=250, antes do Step Aguarda Nome (Y=300)
        "id": "validar-nome",
        "name": "ValidarNome",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "vn-1",
                    "leftValue": "={{ $json.nome_valido }}",
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
        "position": [700, 250],
        "id": "nome-valido",
        "name": "Nome Valido?",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "srn1", "name": "resposta_bot",
                     "value": "Hmm, pode mandar seu nome completo? Ex: Joao Silva",
                     "type": "string"},
                    {"id": "srn2", "name": "proximo_nodo", "value": "aguarda_nome", "type": "string"},
                    {"id": "srn3", "name": "novas_vars",
                     "value": "={{ $node['DetectarPedidoHumano'].json.dados }}", "type": "object"},
                    {"id": "srn4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [950, 350],
        "id": "step-reasking-nome",
        "name": "Step Reasking Nome",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()
existing = {n['name'] for n in wf['nodes']}
if 'ValidarNome' in existing:
    print('Ja existe.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Atualizar Step Aguarda Nome pra usar nome_formatado
for n in wf['nodes']:
    if n.get('name') == 'Step Aguarda Nome':
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'novas_vars':
                a['value'] = ("={{ Object.assign({}, $node['DetectarPedidoHumano'].json.dados, "
                              "{ nome: $node['ValidarNome'].json.nome_formatado }) }}")
                print('Step Aguarda Nome: agora salva nome_formatado (capitalized, truncado)')

# Conexoes: Switch[aguarda_nome] -> ValidarNome -> Nome Valido? -> (true: Step Aguarda Nome / false: Step Reasking Nome)
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
for i, rule in enumerate(switch_node['parameters']['rules']['values']):
    if rule.get('outputKey') == 'aguarda_nome':
        switch_outs[i] = [{'node': 'ValidarNome', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]=aguarda_nome -> ValidarNome (em vez de Step Aguarda Nome direto)')

conns['ValidarNome'] = {'main': [[{'node': 'Nome Valido?', 'type': 'main', 'index': 0}]]}
conns['Nome Valido?'] = {
    'main': [
        [{'node': 'Step Aguarda Nome', 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking Nome', 'type': 'main', 'index': 0}],
    ]
}
conns['Step Reasking Nome'] = {'main': [[{'node': 'SmartSkip', 'type': 'main', 'index': 0}]]}

# Atualizar PegarRespostaBot
for n in wf['nodes']:
    if n.get('name') == 'PegarRespostaBot':
        code = n['parameters']['jsCode']
        if 'Step Reasking Nome' not in code:
            code = code.replace("'Step Aguarda Nome',", "'Step Aguarda Nome', 'Step Reasking Nome',")
            n['parameters']['jsCode'] = code
            print('PegarRespostaBot: incluido Step Reasking Nome')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT {r.status_code}')
