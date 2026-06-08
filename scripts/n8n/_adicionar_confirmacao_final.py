"""
Adiciona resumo + confirmacao final antes de concluir.

Antes: aguarda_email -> concluido (direto)
Depois: aguarda_email -> aguarda_confirmacao_final -> (sim: concluido / nao: reiniciar)

Steps modificados:
- Step Aguarda Email (Final): resposta_bot mostra resumo, proximo_nodo=aguarda_confirmacao_final
- Step Aguarda Email (via IA): mesmo

Nodos novos:
- ClassificarConfirmacaoFinal (code) — yes/no
- Confirmou Final? (Switch sim/nao/fallback)
- Step Final Concluido (concluido + envia Hubtrix)
- Step Final Reiniciar (apaga dados + volta pra inicio)
- Step Reasking Confirma Final
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

# Mesmo code do ClassificarConfirmacao
CLASSIFICAR_CODE = '''// ClassificarConfirmacaoFinal
let raw = '';
try { raw = $('Entrada').first().json.mensagem || ''; } catch(e) {}
const m = String(raw).trim().toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
const SIMs = ['sim', 's', 'isso', 'confirmo', 'correto', 'ok', 'beleza', 'positivo', 'ta', 'yes', '👍', 'confirma', 'fechado', 'pode', 'pode enviar'];
const NAOs = ['nao', 'n', 'errado', 'incorreto', 'negativo', 'no', 'nope', 'editar', 'corrigir', 'mudar', 'voltar', '👎'];
let r = 'unknown';
if (SIMs.some(w => m === w || m.startsWith(w + ' '))) r = 'sim';
else if (NAOs.some(w => m === w || m.startsWith(w + ' '))) r = 'nao';
return [{ json: { confirmacao: r, mensagem_norm: m } }];'''

# Resumo bonito com todos os campos da session
RESUMO_EXPR = ("=Otimo! Antes de eu enviar pra equipe, confere se ta tudo certo:\n\n"
               "👤 *Nome:* {{ $node['Load Session'].json.dados.nome }}\n"
               "📧 *Email:* {{ (() => { try { return $('ResultadoIA').first().json.response.formattedValue || $node['Load Session'].json.dados.email || $node['Entrada'].json.mensagem; } catch(e) { return $node['Entrada'].json.mensagem; } })() }}\n"
               "🆔 *CPF:* {{ $node['Load Session'].json.dados.cpf }}\n"
               "🎂 *Nascimento:* {{ $node['Load Session'].json.dados.data_nascimento }}\n\n"
               "📍 *Endereco:*\n"
               "   {{ $node['Load Session'].json.dados.numero }} {{ $node['Load Session'].json.dados.complemento ? '- ' + $node['Load Session'].json.dados.complemento : '' }}\n"
               "   {{ $node['Load Session'].json.dados.bairro }} - {{ $node['Load Session'].json.dados.cidade }}/{{ $node['Load Session'].json.dados.estado }}\n"
               "   CEP: {{ $node['Load Session'].json.dados.cep }}\n\n"
               "📡 *Plano:* {{ $node['Load Session'].json.dados.plano_interesse }}\n\n"
               "Posso confirmar? (sim/nao)")

NODES_NEW = [
    {
        "parameters": {"jsCode": CLASSIFICAR_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-640, 1800],
        "id": "classificar-conf-final",
        "name": "ClassificarConfirmacaoFinal",
    },
    {
        "parameters": {
            "rules": {
                "values": [
                    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                     "conditions": [{"id": "cf-sim", "leftValue": "={{ $json.confirmacao }}", "rightValue": "sim",
                                     "operator": {"type": "string", "operation": "equals"}}],
                     "combinator": "and"}, "renameOutput": True, "outputKey": "sim"},
                    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                     "conditions": [{"id": "cf-nao", "leftValue": "={{ $json.confirmacao }}", "rightValue": "nao",
                                     "operator": {"type": "string", "operation": "equals"}}],
                     "combinator": "and"}, "renameOutput": True, "outputKey": "nao"},
                ]
            },
            "looseTypeValidation": True,
            "options": {"fallbackOutput": "extra"},
        },
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [-400, 1800],
        "id": "confirmou-final",
        "name": "Confirmou Final?",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sfc1", "name": "resposta_bot",
                     "value": "Perfeito! ✅ Seus dados foram registrados. Um consultor da Vero entra em contato em ate 24h pra finalizar a contratacao. Obrigado!",
                     "type": "string"},
                    {"id": "sfc2", "name": "proximo_nodo", "value": "concluido", "type": "string"},
                    {"id": "sfc3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "sfc4", "name": "deve_enviar_hubtrix", "value": "=true", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 1750],
        "id": "step-final-concluido",
        "name": "Step Final Concluido",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sfr1", "name": "resposta_bot",
                     "value": "Sem problema! Vamos comecar de novo entao. Qual o seu nome?",
                     "type": "string"},
                    {"id": "sfr2", "name": "proximo_nodo", "value": "aguarda_nome", "type": "string"},
                    {"id": "sfr3", "name": "novas_vars", "value": "={{ ({}) }}", "type": "object"},
                    {"id": "sfr4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 1850],
        "id": "step-final-reiniciar",
        "name": "Step Final Reiniciar",
    },
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "srf1", "name": "resposta_bot",
                     "value": "Nao entendi 😅 Responde 'sim' pra confirmar ou 'nao' pra editar.",
                     "type": "string"},
                    {"id": "srf2", "name": "proximo_nodo", "value": "aguarda_confirmacao_final", "type": "string"},
                    {"id": "srf3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "srf4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-160, 1950],
        "id": "step-reasking-confirma-final",
        "name": "Step Reasking Confirma Final",
    },
]

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'ClassificarConfirmacaoFinal' in existing:
    print('Ja existe. Abortando.')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Atualiza Step Aguarda Email (Final) e Step Aguarda Email (via IA):
# resposta_bot = resumo, proximo_nodo = aguarda_confirmacao_final
for n in wf['nodes']:
    if n.get('name') in ('Step Aguarda Email (Final)', 'Step Aguarda Email (via IA)'):
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'resposta_bot':
                a['value'] = RESUMO_EXPR
            elif a.get('name') == 'proximo_nodo':
                a['value'] = 'aguarda_confirmacao_final'
            elif a.get('name') == 'novas_vars':
                # salva email pra dados antes de mostrar resumo
                if n['name'] == 'Step Aguarda Email (Final)':
                    a['value'] = ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                                  "{ email: $node['Entrada'].json.mensagem }) }}")
                else:
                    a['value'] = ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                                  "{ email: $node['ResultadoIA'].json.response.formattedValue }) }}")
            elif a.get('name') == 'deve_enviar_hubtrix':
                a['value'] = '=false'  # nao envia ainda — espera confirmacao
        print(f'{n["name"]} atualizado: agora mostra resumo + vai pra aguarda_confirmacao_final')

# Switch: add aguarda_confirmacao_final
switch_node = next((n for n in wf['nodes'] if n['name'] == 'Por Nodo Atual'), None)
rules = switch_node['parameters']['rules']['values']
keys = {r.get('outputKey') for r in rules}
if 'aguarda_confirmacao_final' not in keys:
    rules.append({
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "sw-confirma-final",
                "leftValue": "={{ $json.nodo_atual }}",
                "rightValue": "aguarda_confirmacao_final",
                "operator": {"type": "string", "operation": "equals"},
            }],
            "combinator": "and",
        },
        "renameOutput": True,
        "outputKey": "aguarda_confirmacao_final",
    })
    print('Switch: adicionada rule aguarda_confirmacao_final')

# Connections
conns = wf['connections']
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
while len(switch_outs) < len(rules):
    switch_outs.append([])
for i, rule in enumerate(rules):
    if rule.get('outputKey') == 'aguarda_confirmacao_final':
        switch_outs[i] = [{'node': 'ClassificarConfirmacaoFinal', 'type': 'main', 'index': 0}]
        print(f'Switch[{i}]=aguarda_confirmacao_final -> ClassificarConfirmacaoFinal')

conns['ClassificarConfirmacaoFinal'] = {'main': [[{'node': 'Confirmou Final?', 'type': 'main', 'index': 0}]]}
conns['Confirmou Final?'] = {
    'main': [
        [{'node': 'Step Final Concluido', 'type': 'main', 'index': 0}],
        [{'node': 'Step Final Reiniciar', 'type': 'main', 'index': 0}],
        [{'node': 'Step Reasking Confirma Final', 'type': 'main', 'index': 0}],
    ]
}
conns['Step Final Concluido'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Final Reiniciar'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Reasking Confirma Final'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'\nPUT {r.status_code}')
print('\nFluxo final: email -> aguarda_confirmacao_final -> mostra resumo -> sim:concluido / nao:reiniciar')
