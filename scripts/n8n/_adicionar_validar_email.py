"""
Adiciona validacao de email no workflow Vero:
- ValidarEmail (code node) lendo $json.mensagem
- IF Email Valido?
- Step Reasking Email (mantem estado aguarda_email, mensagem de erro)

Reorganiza connections:
  Por Nodo Atual [output aguarda_email]
    -> ValidarEmail
      -> Email Valido?
        ├─ true  -> Step Aguarda Email (Final)
        └─ false -> Step Reasking Email -> Save Session
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

EMAIL_CODE = '''// ValidarEmail — adaptado do Matrix
// Le a mensagem do nodo Entrada (no ponto do fluxo $json e a saida do Switch, sem campo mensagem)
const mensagem = $('Entrada').first().json.mensagem;
for (const item of $input.all()) {
  const emailString = mensagem ? String(mensagem).trim() : null;
  item.json.isValidEmail = false;
  item.json.validationError = null;

  if (!emailString) {
    item.json.validationError = "Email vazio";
    continue;
  }

  const regex = /^(([^<>()[\\]\\\\.,;:\\s@"]+(\\.[^<>()[\\]\\\\.,;:\\s@"]+)*)|(".+"))@((\\[[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\])|(([a-zA-Z\\-0-9]+\\.)+[a-zA-Z]{2,}))$/;

  if (!regex.test(emailString)) {
    item.json.validationError = "Formato de email invalido";
    continue;
  }

  item.json.isValidEmail = true;
}
return $input.all();'''

# Posicoes (aproximadas, refletindo o canvas atual)
NODES_NEW = [
    {
        "parameters": {"jsCode": EMAIL_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-280, -150],  # antes do Step Aguarda Email
        "id": "validar-email",
        "name": "ValidarEmail",
    },
    {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "loose",
                    "version": 2,
                },
                "conditions": [
                    {
                        "id": "ve-1",
                        "leftValue": "={{ $json.isValidEmail }}",
                        "rightValue": "",
                        "operator": {
                            "type": "boolean",
                            "operation": "true",
                            "singleValue": True,
                        },
                    }
                ],
                "combinator": "and",
            },
            "looseTypeValidation": True,
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [-100, -150],
        "id": "email-valido",
        "name": "Email Valido?",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {
                        "id": "re1",
                        "name": "resposta_bot",
                        "value": "Hmm, esse email parece estar com problema. Pode mandar de novo? Exemplo: joao@gmail.com",
                        "type": "string",
                    },
                    {
                        "id": "re2",
                        "name": "proximo_nodo",
                        "value": "aguarda_email",
                        "type": "string",
                    },
                    {
                        "id": "re3",
                        "name": "novas_vars",
                        "value": "={{ $node['Load Session'].json.dados }}",
                        "type": "object",
                    },
                    {
                        "id": "re4",
                        "name": "deve_enviar_hubtrix",
                        "value": "=false",
                        "type": "boolean",
                    },
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [80, -50],  # ramo "false" do IF
        "id": "step-reasking-email",
        "name": "Step Reasking Email",
    },
]

# GET workflow
r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

# Aborta se ja existe
existing_names = {n['name'] for n in wf['nodes']}
if 'ValidarEmail' in existing_names:
    print('ValidarEmail ja existe. Abortando (idempotencia).')
    sys.exit(0)

# Adiciona nodos
wf['nodes'].extend(NODES_NEW)

# Reorganiza connections:
# Por Nodo Atual sai de seus outputs em ordem das rules.
# Pela analise do Switch, output[4] e aguarda_email (Step Aguarda Email Final)
# Vou achar quais sao os outputs do Switch que vao pra Step Aguarda Email (Final)
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
target_step_final = 'Step Aguarda Email (Final)'

# Acha qual output do switch aponta pra Step Aguarda Email (Final)
out_idx_email = None
for i, outs in enumerate(switch_outs):
    for tgt in (outs or []):
        if tgt.get('node') == target_step_final:
            out_idx_email = i
            break
    if out_idx_email is not None:
        break

print(f'Output do switch que vai pra {target_step_final}: index={out_idx_email}')

if out_idx_email is None:
    raise SystemExit('Nao encontrei conexao Switch -> Step Aguarda Email (Final)')

# Reescreve: aquele output vai pra ValidarEmail agora
switch_outs[out_idx_email] = [{'node': 'ValidarEmail', 'type': 'main', 'index': 0}]

# Conecta ValidarEmail -> Email Valido?
conns['ValidarEmail'] = {'main': [[{'node': 'Email Valido?', 'type': 'main', 'index': 0}]]}

# Conecta Email Valido? -> output 0 (true) Step Aguarda Email Final, output 1 (false) Step Reasking Email
conns['Email Valido?'] = {
    'main': [
        [{'node': target_step_final, 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking Email', 'type': 'main', 'index': 0}],
    ]
}

# Conecta Step Reasking Email -> Save Session (ja existe)
conns['Step Reasking Email'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

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
print(f'active: {r.json().get("active")}')
print('\nNodos adicionados: ValidarEmail + Email Valido? + Step Reasking Email')
print('Conexoes:')
print('  Por Nodo Atual [aguarda_email] -> ValidarEmail -> Email Valido?')
print('    true  -> Step Aguarda Email (Final)')
print('    false -> Step Reasking Email -> Save Session')
