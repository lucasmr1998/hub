"""
Adiciona estados aguarda_cpf e aguarda_data_nasc entre plano e email.

Fluxo final: cep -> numero -> complemento -> plano -> cpf -> data_nasc -> email -> concluido

Validacoes:
- CPF: Camada 1 = regex 11 digitos + algoritmo dig verificador; Camada 2 = IA
- Data Nasc: Camada 1 = regex DD/MM/AAAA + maioridade; Camada 2 = IA

Reusa: IA Validator Universal, Router IA Tipo, Router IA Tipo Erro
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

VALIDAR_CPF_CODE = '''// ValidarCPF — regex 11 digitos + algoritmo dig verificador
let raw = '';
try { raw = $('Entrada').first().json.mensagem || ''; } catch(e) {}
const limpo = String(raw).replace(/\\D/g, '');
let valido = false;
if (limpo.length === 11 && !/^(\\d)\\1{10}$/.test(limpo)) {
  // Algoritmo CPF
  let soma1 = 0, soma2 = 0;
  for (let i = 0; i < 9; i++) {
    soma1 += parseInt(limpo[i]) * (10 - i);
    soma2 += parseInt(limpo[i]) * (11 - i);
  }
  let d1 = (soma1 * 10) % 11;
  if (d1 === 10) d1 = 0;
  soma2 += d1 * 2;
  let d2 = (soma2 * 10) % 11;
  if (d2 === 10) d2 = 0;
  valido = (d1 === parseInt(limpo[9]) && d2 === parseInt(limpo[10]));
}
return [{ json: {
  cpf_input: raw,
  cpf_limpo: limpo,
  cpf_valido: valido,
}}];'''

VALIDAR_DATA_NASC_CODE = '''// ValidarDataDeNascimento — regex DD/MM/AAAA + maioridade
let raw = '';
try { raw = $('Entrada').first().json.mensagem || ''; } catch(e) {}
const s = String(raw).trim();
const re = /^(\\d{1,2})[\\/\\-\\.](\\d{1,2})[\\/\\-\\.](\\d{2,4})$/;
const m = s.match(re);
let valido = false;
let formatted = '';
let isOver18 = false;
if (m) {
  let d = parseInt(m[1]), mes = parseInt(m[2]), a = parseInt(m[3]);
  if (a < 100) a += (a > 50 ? 1900 : 2000);
  const dt = new Date(a, mes - 1, d);
  if (dt.getFullYear() === a && dt.getMonth() === mes - 1 && dt.getDate() === d) {
    valido = true;
    formatted = `${String(d).padStart(2,'0')}/${String(mes).padStart(2,'0')}/${a}`;
    const hoje = new Date();
    const idade = hoje.getFullYear() - a - ((hoje.getMonth() < mes - 1 || (hoje.getMonth() === mes - 1 && hoje.getDate() < d)) ? 1 : 0);
    isOver18 = idade >= 18;
  }
}
return [{ json: {
  data_input: raw,
  data_formatted: formatted,
  data_valida: valido,
  is_over_18: isOver18,
  camada1_ok: valido && isOver18,
}}];'''

NODES_NEW = [
    # === CPF ===
    {
        "parameters": {"jsCode": VALIDAR_CPF_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-640, 1400],
        "id": "validar-cpf",
        "name": "ValidarCPF",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "cv-1",
                    "leftValue": "={{ $json.cpf_valido }}",
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
        "position": [-400, 1400],
        "id": "cpf-valido",
        "name": "CPF Valido?",
    },
    # Step Aguarda CPF — happy path (Camada 1)
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "scpf1", "name": "resposta_bot",
                     "value": "Otimo! Qual sua data de nascimento? (formato dd/mm/aaaa)",
                     "type": "string"},
                    {"id": "scpf2", "name": "proximo_nodo", "value": "aguarda_data_nasc", "type": "string"},
                    {"id": "scpf3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ cpf: $node['ValidarCPF'].json.cpf_limpo }) }}"),
                     "type": "object"},
                    {"id": "scpf4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 1400],
        "id": "step-aguarda-cpf",
        "name": "Step Aguarda CPF",
    },
    # Step Aguarda CPF (via IA)
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "scpfi1", "name": "resposta_bot",
                     "value": "Otimo! Qual sua data de nascimento? (formato dd/mm/aaaa)",
                     "type": "string"},
                    {"id": "scpfi2", "name": "proximo_nodo", "value": "aguarda_data_nasc", "type": "string"},
                    {"id": "scpfi3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ cpf: String($node['ResultadoIA'].json.response.formattedValue || '').replace(/\\D/g, '') }) }}"),
                     "type": "object"},
                    {"id": "scpfi4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [1600, 1600],
        "id": "step-aguarda-cpf-via-ia",
        "name": "Step Aguarda CPF (via IA)",
    },
    # Contexto CPF
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "ccpf1", "name": "tipo", "value": "cpf", "type": "string"},
                    {"id": "ccpf2", "name": "pergunta", "value": "Qual o seu CPF?", "type": "string"},
                    {"id": "ccpf3", "name": "resposta",
                     "value": "={{ $node['Entrada'].json.mensagem }}", "type": "string"},
                    {"id": "ccpf4", "name": "contexto",
                     "value": "CPF tem 11 digitos. Tolerar formato 000.000.000-00 ou apenas digitos. Recusar se nao tiver 11 numeros. formattedValue retorna 11 digitos sem pontuacao.",
                     "type": "string"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [560, 1200],
        "id": "contexto-cpf",
        "name": "Contexto CPF",
    },
    # Step Reasking CPF
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "srcpf1", "name": "resposta_bot",
                     "value": "={{ $node['ResultadoIA'].json.response.errorMessage || 'CPF nao reconhecido. Pode mandar os 11 digitos?' }}",
                     "type": "string"},
                    {"id": "srcpf2", "name": "proximo_nodo", "value": "aguarda_cpf", "type": "string"},
                    {"id": "srcpf3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "srcpf4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [1600, 1700],
        "id": "step-reasking-cpf",
        "name": "Step Reasking CPF",
    },

    # === DATA DE NASCIMENTO ===
    {
        "parameters": {"jsCode": VALIDAR_DATA_NASC_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-640, 1600],
        "id": "validar-data-nasc",
        "name": "ValidarDataDeNascimento",
    },
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "dv-1",
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
        "position": [-400, 1600],
        "id": "data-valida",
        "name": "Data Valida?",
    },
    # Step Aguarda Data Nasc — happy path
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sdn1", "name": "resposta_bot",
                     "value": "Quase pronto! Pra fechar, qual o seu email?",
                     "type": "string"},
                    {"id": "sdn2", "name": "proximo_nodo", "value": "aguarda_email", "type": "string"},
                    {"id": "sdn3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ data_nascimento: $node['ValidarDataDeNascimento'].json.data_formatted }) }}"),
                     "type": "object"},
                    {"id": "sdn4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 1600],
        "id": "step-aguarda-data-nasc",
        "name": "Step Aguarda Data Nasc",
    },
    # Step Aguarda Data Nasc (via IA)
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sdni1", "name": "resposta_bot",
                     "value": "Quase pronto! Pra fechar, qual o seu email?",
                     "type": "string"},
                    {"id": "sdni2", "name": "proximo_nodo", "value": "aguarda_email", "type": "string"},
                    {"id": "sdni3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ data_nascimento: $node['ResultadoIA'].json.response.formattedValue }) }}"),
                     "type": "object"},
                    {"id": "sdni4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [1600, 1800],
        "id": "step-aguarda-data-nasc-via-ia",
        "name": "Step Aguarda Data Nasc (via IA)",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "cdn1", "name": "tipo", "value": "data_nasc", "type": "string"},
                    {"id": "cdn2", "name": "pergunta", "value": "Qual sua data de nascimento?", "type": "string"},
                    {"id": "cdn3", "name": "resposta",
                     "value": "={{ $node['Entrada'].json.mensagem }}", "type": "string"},
                    {"id": "cdn4", "name": "contexto",
                     "value": "Data no formato DD/MM/AAAA. Tolerar variacoes (DD-MM-AAAA, DD.MM.AAAA). Cliente deve ter ao menos 18 anos. formattedValue retorna DD/MM/AAAA. Se < 18 anos, errorMessage explica.",
                     "type": "string"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [800, 1200],
        "id": "contexto-data-nasc",
        "name": "Contexto Data Nasc",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "srdn1", "name": "resposta_bot",
                     "value": "={{ $node['ResultadoIA'].json.response.errorMessage || 'Data nao reconhecida. Manda no formato dd/mm/aaaa, por favor.' }}",
                     "type": "string"},
                    {"id": "srdn2", "name": "proximo_nodo", "value": "aguarda_data_nasc", "type": "string"},
                    {"id": "srdn3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "srdn4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [1600, 1900],
        "id": "step-reasking-data-nasc",
        "name": "Step Reasking Data Nasc",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'ValidarCPF' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Atualizar Step Aguarda Plano e Step Aguarda Plano (via IA) — agora vao pra aguarda_cpf
for n in wf['nodes']:
    if n.get('name') in ('Step Aguarda Plano', 'Step Aguarda Plano (via IA)'):
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'proximo_nodo':
                a['value'] = 'aguarda_cpf'
                print(f'{n["name"]}: proximo_nodo -> aguarda_cpf')
            elif a.get('name') == 'resposta_bot':
                a['value'] = ("=Otima escolha! 👍 Plano selecionado: {{ "
                              "(() => { try { return $node['ValidarEscolhaPlano'].json.plano_match_label; } catch(e) {} "
                              "try { return $node['Load Session'].json.dados.plano_interesse; } catch(e) {} "
                              "return 'plano'; })() }}.\n\n"
                              "Pra fechar, qual o seu CPF?")

# Atualizar Switch — adicionar rules pra aguarda_cpf e aguarda_data_nasc
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
rules = switch_node['parameters']['rules']['values']
existing_keys = {r.get('outputKey') for r in rules}
for novo in ['aguarda_cpf', 'aguarda_data_nasc']:
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

# Connections
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
while len(switch_outs) < len(rules):
    switch_outs.append([])

for i, rule in enumerate(rules):
    if rule.get('outputKey') == 'aguarda_cpf':
        switch_outs[i] = [{'node': 'ValidarCPF', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]=aguarda_cpf -> ValidarCPF')
    elif rule.get('outputKey') == 'aguarda_data_nasc':
        switch_outs[i] = [{'node': 'ValidarDataDeNascimento', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]=aguarda_data_nasc -> ValidarDataDeNascimento')

# Pipeline CPF
conns['ValidarCPF'] = {'main': [[{'node': 'CPF Valido?', 'type': 'main', 'index': 0}]]}
conns['CPF Valido?'] = {
    'main': [
        [{'node': 'Step Aguarda CPF', 'type': 'main', 'index': 0}],     # true
        [{'node': 'Contexto CPF', 'type': 'main', 'index': 0}],         # false -> Camada 2
    ]
}
conns['Contexto CPF'] = {'main': [[{'node': 'IA Validator Universal', 'type': 'main', 'index': 0}]]}
conns['Step Aguarda CPF'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Aguarda CPF (via IA)'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking CPF'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# Pipeline Data Nasc
conns['ValidarDataDeNascimento'] = {'main': [[{'node': 'Data Valida?', 'type': 'main', 'index': 0}]]}
conns['Data Valida?'] = {
    'main': [
        [{'node': 'Step Aguarda Data Nasc', 'type': 'main', 'index': 0}],
        [{'node': 'Contexto Data Nasc', 'type': 'main', 'index': 0}],
    ]
}
conns['Contexto Data Nasc'] = {'main': [[{'node': 'IA Validator Universal', 'type': 'main', 'index': 0}]]}
conns['Step Aguarda Data Nasc'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Aguarda Data Nasc (via IA)'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking Data Nasc'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# Atualizar Routers IA Tipo / Erro pra incluir cpf e data_nasc
EXPR_TIPO = ("={{ (() => { "
             "try { return $('Contexto Email').first().json.tipo; } catch(e) {} "
             "try { return $('Contexto CEP').first().json.tipo; } catch(e) {} "
             "try { return $('Contexto Plano').first().json.tipo; } catch(e) {} "
             "try { return $('Contexto CPF').first().json.tipo; } catch(e) {} "
             "try { return $('Contexto Data Nasc').first().json.tipo; } catch(e) {} "
             "return ''; "
             "})() }}")

for router_name in ['Router IA Tipo', 'Router IA Tipo Erro']:
    n = next((x for x in wf['nodes'] if x['name'] == router_name), None)
    if not n: continue
    rules_r = n['parameters']['rules']['values']
    keys = {r.get('outputKey') for r in rules_r}
    # atualiza expressions existentes
    for rule in rules_r:
        for c in rule['conditions']['conditions']:
            c['leftValue'] = EXPR_TIPO
    # adiciona cpf e data_nasc
    for novo in ['cpf', 'data_nasc']:
        if novo not in keys:
            rules_r.append({
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                    "conditions": [{
                        "id": f"r-{novo}-{router_name[-3:]}",
                        "leftValue": EXPR_TIPO,
                        "rightValue": novo,
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                    "combinator": "and",
                },
                "renameOutput": True,
                "outputKey": novo,
            })
            print(f'{router_name}: adicionada regra {novo}')

# Reescrever conexoes dos Routers
conns['Router IA Tipo'] = {
    'main': [
        [{'node': 'Step Aguarda Email (via IA)', 'type': 'main', 'index': 0}],   # email
        [{'node': 'CEP Resolvido IA', 'type': 'main', 'index': 0}],              # cep
        [{'node': 'Step Aguarda Plano (via IA)', 'type': 'main', 'index': 0}],   # plano
        [{'node': 'Step Aguarda Email (via IA)', 'type': 'main', 'index': 0}],   # fallback (extra)
        [{'node': 'Step Aguarda CPF (via IA)', 'type': 'main', 'index': 0}],     # cpf
        [{'node': 'Step Aguarda Data Nasc (via IA)', 'type': 'main', 'index': 0}], # data_nasc
    ]
}
conns['Router IA Tipo Erro'] = {
    'main': [
        [{'node': 'Step Reasking Email (via IA)', 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking CEP (via IA)', 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking Plano', 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking Email (via IA)', 'type': 'main', 'index': 0}],  # fallback
        [{'node': 'Step Reasking CPF', 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking Data Nasc', 'type': 'main', 'index': 0}],
    ]
}

# PUT
allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code} updatedAt={r.json().get("updatedAt") if r.status_code<300 else r.text[:500]}')
print('\nFluxo final: nome -> cep -> numero -> complemento -> plano -> cpf -> data_nasc -> email -> concluido')
