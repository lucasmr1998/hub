"""
Melhora UX da confirmacao final: quando cliente diz 'nao', perguntar QUAL campo corrigir
em vez de reiniciar tudo.

1. Step Final Reiniciar muda: agora pergunta "o que quer corrigir?"
2. Novo estado: aguarda_decisao_correcao
3. ClassificarCampoCorrigir (code): detecta keyword e retorna campo
4. Switch RouterCorrecao: vai pro estado aguarda_X correspondente (limpa so esse campo)
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

# Code que detecta qual campo cliente quer corrigir
CLASSIFICAR_CAMPO_CODE = '''// ClassificarCampoCorrigir — detecta qual campo cliente quer ajustar
let raw = '';
try { raw = $('Entrada').first().json.mensagem || ''; } catch(e) {}
const m = String(raw).trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');

const MAPA = {
  nome:        ['nome', 'meu nome'],
  cep:         ['cep', 'endereco', 'endereço', 'cidade', 'bairro', 'rua'],
  numero:      ['numero', 'número', 'numero da casa'],
  complemento: ['complemento', 'apto', 'apartamento', 'bloco'],
  plano:       ['plano', 'mega', 'pacote', 'internet'],
  cpf:         ['cpf', 'documento'],
  data_nasc:   ['data', 'nascimento', 'data de nascimento', 'idade', 'aniversario'],
  email:       ['email', 'e-mail', 'mail'],
  rg:          ['rg', 'foto', 'identidade', 'cnh', 'documento'],
};

let campo_alvo = null;
for (const [campo, keywords] of Object.entries(MAPA)) {
  for (const kw of keywords) {
    if (m === kw || m.includes(' ' + kw) || m.includes(kw + ' ') || m.startsWith(kw)) {
      campo_alvo = campo;
      break;
    }
  }
  if (campo_alvo) break;
}

return [{ json: {
  ...$input.first().json,
  campo_alvo: campo_alvo || 'desconhecido',
}}];'''

NODES_NEW = [
    {
        "parameters": {"jsCode": CLASSIFICAR_CAMPO_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-720, 2700],
        "id": "classificar-campo-corrigir",
        "name": "ClassificarCampoCorrigir",
    },
    # Switch que roteia por campo_alvo
    {
        "parameters": {
            "rules": {"values": [
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-nome", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "nome",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "nome"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-cep", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "cep",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "cep"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-num", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "numero",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "numero"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-comp", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "complemento",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "complemento"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-plano", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "plano",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "plano"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-cpf", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "cpf",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "cpf"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-data", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "data_nasc",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "data_nasc"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-email", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "email",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "email"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                 "conditions": [{"id": "rc-rg", "leftValue": "={{ $json.campo_alvo }}", "rightValue": "rg",
                                 "operator": {"type": "string", "operation": "equals"}}],
                 "combinator": "and"}, "renameOutput": True, "outputKey": "rg"},
            ]},
            "looseTypeValidation": True, "options": {"fallbackOutput": "extra"},
        },
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [-480, 2700],
        "id": "router-correcao",
        "name": "Router Correcao",
    },
]

# Steps de voltar pra cada estado (zera o campo + manda pra estado correto)
# Helper: cria Step pra cada campo
def make_step_correcao(slug, pergunta, proximo_estado, campos_limpar):
    """campos_limpar: lista de chaves a deletar de dados antes de voltar"""
    deletes = ' '.join(f"delete d.{c};" for c in campos_limpar)
    return {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": f"sc-{slug}-1", "name": "resposta_bot", "value": pergunta, "type": "string"},
                    {"id": f"sc-{slug}-2", "name": "proximo_nodo", "value": proximo_estado, "type": "string"},
                    {"id": f"sc-{slug}-3", "name": "novas_vars",
                     "value": ("={{ (() => { const d = Object.assign({}, $node['DetectarPedidoHumano'].json.dados); "
                               f"{deletes} return d; }})() }}"),
                     "type": "object"},
                    {"id": f"sc-{slug}-4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-240, 2400 + len([1])*70],
        "id": f"step-corrigir-{slug}",
        "name": f"Step Corrigir {slug.capitalize().replace('_', ' ')}",
    }

CORRECOES = [
    ('nome',        'Tudo bem! Qual seu nome completo?',          'aguarda_nome',                 ['nome']),
    ('cep',         'Sem problema! Qual o CEP correto?',          'aguarda_cep',                  ['cep','cidade','estado','bairro','numero','complemento']),
    ('numero',      'Qual o numero correto da casa?',             'aguarda_numero',               ['numero']),
    ('complemento', 'Qual o complemento correto?',                'aguarda_complemento',          ['complemento']),
    ('plano',       'Qual plano voce quer? Manda o numero ou descreve.', 'aguarda_plano',         ['plano_id','plano_interesse']),
    ('cpf',         'Pode mandar o CPF correto?',                 'aguarda_cpf',                  ['cpf']),
    ('data_nasc',   'Qual a data de nascimento correta? (dd/mm/aaaa)', 'aguarda_data_nasc',       ['data_nascimento']),
    ('email',       'Manda o email correto?',                     'aguarda_email',                ['email']),
    ('rg',          'Manda a foto da frente do RG (ou CNH) novamente.', 'aguarda_doc_rg_frente', ['doc_rg_frente_url','doc_rg_verso_url']),
]

for slug, pergunta, estado, campos in CORRECOES:
    NODES_NEW.append(make_step_correcao(slug, pergunta, estado, campos))

# Step Reasking Corrigir (fallback)
NODES_NEW.append({
    "parameters": {
        "assignments": {
            "assignments": [
                {"id": "src1", "name": "resposta_bot",
                 "value": ("Nao entendi qual campo voce quer corrigir 😅\n"
                           "Pode dizer: nome, cep, numero, complemento, plano, cpf, "
                           "data de nascimento, email ou foto do RG."),
                 "type": "string"},
                {"id": "src2", "name": "proximo_nodo", "value": "aguarda_decisao_correcao", "type": "string"},
                {"id": "src3", "name": "novas_vars",
                 "value": "={{ $node['DetectarPedidoHumano'].json.dados }}", "type": "object"},
                {"id": "src4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
            ]
        },
        "options": {},
    },
    "type": "n8n-nodes-base.set",
    "typeVersion": 3.4,
    "position": [-240, 3100],
    "id": "step-reasking-corrigir",
    "name": "Step Reasking Corrigir",
})

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'ClassificarCampoCorrigir' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Modifica Step Final Reiniciar: agora pergunta o que corrigir
for n in wf['nodes']:
    if n.get('name') == 'Step Final Reiniciar':
        for a in n['parameters']['assignments']['assignments']:
            if a['name'] == 'resposta_bot':
                a['value'] = ("Sem problema! O que voce quer corrigir?\n\n"
                              "Pode dizer: *nome*, *cep* (endereco), *numero*, *complemento*, "
                              "*plano*, *cpf*, *data de nascimento*, *email* ou *foto do RG*.")
            elif a['name'] == 'proximo_nodo':
                a['value'] = 'aguarda_decisao_correcao'
            elif a['name'] == 'novas_vars':
                a['value'] = "={{ $node['DetectarPedidoHumano'].json.dados }}"  # mantem dados
        print('Step Final Reiniciar: agora pergunta o que corrigir (mantem dados)')

# Switch: nova rule
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
rules = switch_node['parameters']['rules']['values']
keys = {r.get('outputKey') for r in rules}
if 'aguarda_decisao_correcao' not in keys:
    rules.append({
        "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
         "conditions": [{"id": "sw-corrigir", "leftValue": "={{ $json.nodo_atual }}",
                         "rightValue": "aguarda_decisao_correcao",
                         "operator": {"type": "string", "operation": "equals"}}],
         "combinator": "and"},
        "renameOutput": True, "outputKey": "aguarda_decisao_correcao",
    })
    print('Switch: rule aguarda_decisao_correcao adicionada')

# Connections
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
while len(switch_outs) < len(rules):
    switch_outs.append([])
for i, rule in enumerate(rules):
    if rule.get('outputKey') == 'aguarda_decisao_correcao':
        switch_outs[i] = [{'node': 'ClassificarCampoCorrigir', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]=aguarda_decisao_correcao -> ClassificarCampoCorrigir')

conns['ClassificarCampoCorrigir'] = {'main': [[{'node': 'Router Correcao', 'type': 'main', 'index': 0}]]}

# Router Correcao outputs em ORDEM das rules + fallback
ROUTER_TARGETS = ['nome', 'cep', 'numero', 'complemento', 'plano', 'cpf', 'data_nasc', 'email', 'rg']
target_steps = {
    'nome': 'Step Corrigir Nome',
    'cep': 'Step Corrigir Cep',
    'numero': 'Step Corrigir Numero',
    'complemento': 'Step Corrigir Complemento',
    'plano': 'Step Corrigir Plano',
    'cpf': 'Step Corrigir Cpf',
    'data_nasc': 'Step Corrigir Data nasc',
    'email': 'Step Corrigir Email',
    'rg': 'Step Corrigir Rg',
}
conns['Router Correcao'] = {
    'main': [[{'node': target_steps[t], 'type': 'main', 'index': 0}] for t in ROUTER_TARGETS]
            + [[{'node': 'Step Reasking Corrigir', 'type': 'main', 'index': 0}]]  # fallback
}

# Cada Step Corrigir -> Save Session
for slug, _, _, _ in CORRECOES:
    node_name = f'Step Corrigir {slug.capitalize().replace("_", " ")}'
    conns[node_name] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking Corrigir'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# PegarRespostaBot: incluir os novos steps
for n in wf['nodes']:
    if n.get('name') == 'PegarRespostaBot':
        code = n['parameters']['jsCode']
        novos_nomes = [f"'Step Corrigir {s.capitalize().replace('_', ' ')}'" for s, _, _, _ in CORRECOES]
        novos_nomes.append("'Step Reasking Corrigir'")
        novos_str = ', '.join(novos_nomes) + ','
        if 'Step Corrigir Nome' not in code:
            code = code.replace("'Step Inicio',", f"{novos_str}\n  'Step Inicio',")
            n['parameters']['jsCode'] = code
            print('PegarRespostaBot: incluidos steps de correcao')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
print('\nCorrecao implementada: cliente fala "nao" no resumo -> bot pergunta qual campo -> volta pra esse estado preservando os outros dados')
