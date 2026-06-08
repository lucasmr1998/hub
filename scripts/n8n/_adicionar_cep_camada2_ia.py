"""
Adiciona Camada 2 IA pro CEP:
- Branch 'Formato CEP OK?' false agora vai pra IA (em vez de Reasking direto)
- IA tenta extrair 8 digitos de texto livre ("setenta e quatro mil")
- Se IA OK -> CEP Resolvido IA (Set que expoe cep_limpo) -> ViaCEP (segue fluxo existente)
- Se IA falha -> Step Reasking CEP Formato (com errorMessage da IA)

Reuso: o nodo IA Validator Universal ja existe. So precisa adicionar Contexto CEP + roteamento.
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
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "cc1", "name": "tipo", "value": "cep", "type": "string"},
                    {"id": "cc2", "name": "pergunta", "value": "Qual o seu CEP?", "type": "string"},
                    {"id": "cc3", "name": "resposta",
                     "value": "={{ $node['Entrada'].json.mensagem }}", "type": "string"},
                    {"id": "cc4", "name": "contexto",
                     "value": "Aceitar texto livre que possa virar 8 digitos. Tolerar 'setenta e quatro mil' -> '74000000'. formattedValue retorna 8 digitos sem hifen.",
                     "type": "string"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-240, -1100],   # acima da lane aguarda_cep
        "id": "contexto-cep",
        "name": "Contexto CEP",
    },
    # CEP Resolvido IA — expoe cep_limpo no formato que ViaCEP espera
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "crp1", "name": "cep_limpo",
                     "value": "={{ String($json.response.formattedValue).replace(/\\D/g, '') }}",
                     "type": "string"},
                ]
            },
            "includeOtherFields": True,
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [-100, -1100],
        "id": "cep-resolvido-ia",
        "name": "CEP Resolvido IA",
    },
    # Step Reasking CEP via IA — usa errorMessage da IA
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "src1", "name": "resposta_bot",
                     "value": "={{ $node['ResultadoIA'].json.response.errorMessage || 'Hmm, nao entendi o CEP. Pode mandar no formato 00000-000?' }}",
                     "type": "string"},
                    {"id": "src2", "name": "proximo_nodo", "value": "aguarda_cep", "type": "string"},
                    {"id": "src3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "src4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [100, -1100],
        "id": "step-reasking-cep-via-ia",
        "name": "Step Reasking CEP (via IA)",
    },
]

# GET workflow
r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'Contexto CEP' in existing:
    print('Contexto CEP ja existe. Abortando (idempotencia).')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

conns = wf['connections']

# Reescreve Formato CEP OK? out1 (false) — agora vai pro Contexto CEP em vez de Reasking direto
fc = conns.get('Formato CEP OK?', {}).get('main', [])
if len(fc) < 2:
    raise SystemExit('Formato CEP OK? sem 2 outputs.')
print(f'Formato CEP OK? out1 (false) atual: {fc[1]}')
fc[1] = [{'node': 'Contexto CEP', 'type': 'main', 'index': 0}]

# Pipeline IA pra CEP
# Contexto CEP -> IA Validator Universal -> ResultadoIA -> IA OK?
# IA OK? true  -> CEP Resolvido IA -> ViaCEP (existente)
# IA OK? false -> Step Reasking CEP (via IA)
conns['Contexto CEP'] = {'main': [[{'node': 'IA Validator Universal', 'type': 'main', 'index': 0}]]}
conns['CEP Resolvido IA'] = {'main': [[{'node': 'HTTP ViaCEP', 'type': 'main', 'index': 0}]]}
conns['Step Reasking CEP (via IA)'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# IA OK? hoje aponta pra Step Aguarda Email (via IA)/Reasking Email (via IA).
# Conflito: a IA Universal e compartilhada entre email e cep!
# Solucao: criar IF Roteador-IA que verifica tipo (response.tipo? ou um campo passado no contexto)
# Mais simples: trocar Contexto Email e Contexto CEP pra incluir um "destino" e direcionar
# Pra ja, vou usar um IF que olha o tipo da requisicao via $node lookup.
# Mas como o IA OK? hoje so tem 2 saidas (true/false), preciso quebrar isso.
#
# Estrategia: REMOVER conexoes atuais de IA OK? e adicionar IF Tipo IA antes da bifurcacao
print('\n>>> Inserindo router por tipo apos IA OK? <<<')

# Verifica se ja existe Router IA Tipo
if 'Router IA Tipo' not in existing:
    # Adiciona Router IA Tipo (Switch por tipo)
    router_node = {
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                            "conditions": [
                                {
                                    "id": "ri-email",
                                    "leftValue": "={{ $json.tipo || $node['Contexto Email'].json?.tipo || $node['Contexto CEP'].json?.tipo }}",
                                    "rightValue": "email",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                            "combinator": "and",
                        },
                        "renameOutput": True,
                        "outputKey": "email",
                    },
                    {
                        "conditions": {
                            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                            "conditions": [
                                {
                                    "id": "ri-cep",
                                    "leftValue": "={{ $json.tipo || $node['Contexto Email'].json?.tipo || $node['Contexto CEP'].json?.tipo }}",
                                    "rightValue": "cep",
                                    "operator": {"type": "string", "operation": "equals"},
                                }
                            ],
                            "combinator": "and",
                        },
                        "renameOutput": True,
                        "outputKey": "cep",
                    },
                ]
            },
            "looseTypeValidation": True,
            "options": {"fallbackOutput": "extra"},
        },
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [800, -100],
        "id": "router-ia-tipo",
        "name": "Router IA Tipo",
    }
    wf['nodes'].append(router_node)

# Re-faz a conexao do IA OK? pra ir pro Router primeiro
# IA OK? true  -> Router IA Tipo
#               out 'email' -> Step Aguarda Email (via IA)
#               out 'cep'   -> CEP Resolvido IA
#               fallback    -> Step Aguarda Email (via IA)  (compat)
# IA OK? false -> Router IA Tipo Erro (similar, mas pra reasking)
#
# Pra nao perder a propagacao de tipo entre Contexto-X e IA, vou usar pass-through:
# Os Contexto-X sao Set com 'tipo' definido; o IA Validator Universal pode passar tipo adiante
# pra o ResultadoIA preservar. Mas como o agent so retorna o JSON output, e ResultadoIA so
# parseia $json.output, vamos passar tipo via $node lookup direto no Router.

# Substitui as conexoes existentes de IA OK?
# Faz IA OK? true -> Router IA Tipo (ok)
# Faz IA OK? false -> Router IA Tipo Erro (criar)
ia_ok = conns.get('IA OK?', {}).get('main', [])
print(f'IA OK? out0 atual: {ia_ok[0] if ia_ok else []}')

# Cria Router IA Tipo Erro
if 'Router IA Tipo Erro' not in existing:
    router_err = {
        "parameters": {
            "rules": {
                "values": [
                    {
                        "conditions": {
                            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                            "conditions": [{
                                "id": "rie-email",
                                "leftValue": "={{ $node['Contexto Email'].json?.tipo === 'email' && $node['Contexto CEP'].json?.tipo !== 'cep' ? 'email' : ($node['Contexto CEP'].json?.tipo === 'cep' ? 'cep' : '') }}",
                                "rightValue": "email",
                                "operator": {"type": "string", "operation": "equals"},
                            }],
                            "combinator": "and",
                        },
                        "renameOutput": True,
                        "outputKey": "email",
                    },
                    {
                        "conditions": {
                            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                            "conditions": [{
                                "id": "rie-cep",
                                "leftValue": "={{ $node['Contexto CEP'].json?.tipo }}",
                                "rightValue": "cep",
                                "operator": {"type": "string", "operation": "equals"},
                            }],
                            "combinator": "and",
                        },
                        "renameOutput": True,
                        "outputKey": "cep",
                    },
                ]
            },
            "looseTypeValidation": True,
            "options": {"fallbackOutput": "extra"},
        },
        "type": "n8n-nodes-base.switch",
        "typeVersion": 3.2,
        "position": [800, 50],
        "id": "router-ia-tipo-erro",
        "name": "Router IA Tipo Erro",
    }
    wf['nodes'].append(router_err)

# Reescreve IA OK?
conns['IA OK?'] = {
    'main': [
        [{'node': 'Router IA Tipo', 'type': 'main', 'index': 0}],         # true
        [{'node': 'Router IA Tipo Erro', 'type': 'main', 'index': 0}],    # false
    ]
}

# Router IA Tipo (true branch): out0=email, out1=cep, fallback=extra (out2)
conns['Router IA Tipo'] = {
    'main': [
        [{'node': 'Step Aguarda Email (via IA)', 'type': 'main', 'index': 0}],  # email
        [{'node': 'CEP Resolvido IA', 'type': 'main', 'index': 0}],              # cep
        [{'node': 'Step Aguarda Email (via IA)', 'type': 'main', 'index': 0}],  # fallback
    ]
}

# Router IA Tipo Erro (false branch): out0=email-reasking, out1=cep-reasking, fallback
conns['Router IA Tipo Erro'] = {
    'main': [
        [{'node': 'Step Reasking Email (via IA)', 'type': 'main', 'index': 0}],  # email
        [{'node': 'Step Reasking CEP (via IA)', 'type': 'main', 'index': 0}],    # cep
        [{'node': 'Step Reasking Email (via IA)', 'type': 'main', 'index': 0}],  # fallback
    ]
}

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
print('\nFluxo CEP agora com cascata IA:')
print('  ValidarCepFormato -> Formato CEP OK?')
print('    true  -> ViaCEP (existente)')
print('    false -> Contexto CEP -> IA Validator -> ResultadoIA -> IA OK?')
print('               true  -> Router IA Tipo -> [cep] -> CEP Resolvido IA -> ViaCEP')
print('               false -> Router IA Tipo Erro -> [cep] -> Step Reasking CEP (via IA)')
