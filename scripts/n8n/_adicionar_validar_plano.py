"""
Adiciona validador de PLANO com cascata:
1. GerarCatalogoPlanos (code) — gera lista numerada baseada na cidade (apos validacao CEP)
2. ValidarEscolhaPlano (code) — Camada 1: match numero ("1"-"9"), velocidade ("550","800") exata e unica
3. Plano Valido? (IF)
4. Contexto Plano (Set) — input pro IA Validator
5. Step Reasking Plano + Step Aguarda Plano (via IA)
6. Adiciona branches "plano" nos Routers IA Tipo / Erro

Topologia aguarda_plano:
  Por Nodo Atual [aguarda_plano] -> ValidarEscolhaPlano -> Plano Valido?
                                                            true  -> Step Aguarda Plano (existente)
                                                            false -> Contexto Plano -> IA Validator -> ResultadoIA -> IA OK?
                                                                                                                       true  -> Router IA Tipo [plano] -> Step Aguarda Plano (via IA)
                                                                                                                       false -> Router IA Tipo Erro [plano] -> Step Reasking Plano

Step Aguarda CEP agora chama GerarCatalogoPlanos (insercao entre Atendido? true e Step Aguarda CEP)
e usa lista_formatada na resposta_bot.
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

CATALOGO_CODE = '''// GerarCatalogoPlanos — gera grupo, planos e lista formatada
// Le cidade de duas fontes: HTTP ViaCEP (turno do CEP) ou Load Session.dados.cidade (turno do plano)
function normCidade(s) {
  return (s || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
}
let cidade = '';
try { cidade = $('HTTP ViaCEP').first().json.localidade; } catch(e) {}
if (!cidade) { try { cidade = $('Load Session').first().json.dados.cidade; } catch(e) {} }
const cidadeNorm = normCidade(cidade);

const GRUPO_POR_CIDADE = {
  'agudos': 'A', 'pederneiras': 'A', 'pirajui': 'A', 'piratininga': 'A',
  'americana': 'B', 'bauru': 'B', 'limeira': 'B',
};

const PLANOS = {
  A: [
    {id:'A1', vel:550, label:'550 Mega + Wi-Fi 6', pix:97.90, boleto:107.90},
    {id:'A2', vel:550, label:'550 Mega + Chip 20GB', pix:102.90, boleto:112.90},
    {id:'A3', vel:800, label:'800 Mega + Globoplay + Chip 20GB', pix:139.90, boleto:149.90},
    {id:'A4', vel:800, label:'800 Mega + Disney + ESPN + Chip 20GB', pix:139.90, boleto:149.90},
    {id:'A5', vel:800, label:'800 Mega + Disney + HBO Max + Chip 30GB', pix:149.90, boleto:159.90},
    {id:'A6', vel:800, label:'800 Mega + Globoplay + HBO Max + Chip 60GB', pix:149.90, boleto:159.90},
    {id:'A7', vel:800, label:'800 Mega + Prime + Apple TV + Chip 30GB', pix:149.90, boleto:159.90},
    {id:'A8', vel:800, label:'800 Mega Premium (Prime + AppleTV + HBO + Globoplay + Chip 60GB)', pix:199.90, boleto:209.90},
  ],
  B: [
    {id:'B1', vel:550, label:'550 Mega + Wi-Fi 6', pix:97.90, boleto:107.90},
    {id:'B2', vel:550, label:'550 Mega + Chip 20GB', pix:102.90, boleto:112.90},
    {id:'B3', vel:800, label:'800 Mega + Vero Video Esportes + YouTube Premium + Chip 30GB', pix:129.90, boleto:139.90},
    {id:'B4', vel:800, label:'800 Mega + Globoplay + Chip 20GB', pix:139.90, boleto:149.90},
    {id:'B5', vel:800, label:'800 Mega + Disney + ESPN + Chip 20GB', pix:139.90, boleto:149.90},
    {id:'B6', vel:800, label:'800 Mega + Disney + HBO Max + Chip 30GB', pix:149.90, boleto:159.90},
    {id:'B7', vel:800, label:'800 Mega + Globoplay + HBO Max + Chip 60GB', pix:149.90, boleto:159.90},
    {id:'B8', vel:800, label:'800 Mega + Prime + Apple TV + Chip 30GB', pix:149.90, boleto:159.90},
    {id:'B9', vel:800, label:'800 Mega Premium (Prime + AppleTV + HBO + Globoplay + Chip 60GB)', pix:199.90, boleto:209.90},
  ]
};

const grupo = GRUPO_POR_CIDADE[cidadeNorm] || null;
const planos = grupo ? PLANOS[grupo] : [];
const lista_formatada = planos.length
  ? planos.map((p, i) => `${i+1}. ${p.label} - R$ ${p.pix.toFixed(2).replace('.',',')} (pix) ou R$ ${p.boleto.toFixed(2).replace('.',',')} (boleto)`).join('\\n')
  : '(catalogo nao disponivel pra essa regiao)';

return [{ json: {
  cidade: cidade,
  grupo: grupo,
  planos: planos,
  catalogo_json: JSON.stringify(planos),
  lista_formatada: lista_formatada,
}}];'''

VALIDAR_ESCOLHA_PLANO_CODE = '''// ValidarEscolhaPlano (Camada 1) — matcha numero ou velocidade
function normCidade(s) {
  return (s || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
}
let cidade = '';
try { cidade = $('Load Session').first().json.dados.cidade; } catch(e) {}
const cidadeNorm = normCidade(cidade);

const GRUPO_POR_CIDADE = {
  'agudos': 'A', 'pederneiras': 'A', 'pirajui': 'A', 'piratininga': 'A',
  'americana': 'B', 'bauru': 'B', 'limeira': 'B',
};
const PLANOS = {
  A: [
    {id:'A1', vel:550, label:'550 Mega + Wi-Fi 6', pix:97.90, boleto:107.90},
    {id:'A2', vel:550, label:'550 Mega + Chip 20GB', pix:102.90, boleto:112.90},
    {id:'A3', vel:800, label:'800 Mega + Globoplay + Chip 20GB', pix:139.90, boleto:149.90},
    {id:'A4', vel:800, label:'800 Mega + Disney + ESPN + Chip 20GB', pix:139.90, boleto:149.90},
    {id:'A5', vel:800, label:'800 Mega + Disney + HBO Max + Chip 30GB', pix:149.90, boleto:159.90},
    {id:'A6', vel:800, label:'800 Mega + Globoplay + HBO Max + Chip 60GB', pix:149.90, boleto:159.90},
    {id:'A7', vel:800, label:'800 Mega + Prime + Apple TV + Chip 30GB', pix:149.90, boleto:159.90},
    {id:'A8', vel:800, label:'800 Mega Premium (Prime + AppleTV + HBO + Globoplay + Chip 60GB)', pix:199.90, boleto:209.90},
  ],
  B: [
    {id:'B1', vel:550, label:'550 Mega + Wi-Fi 6', pix:97.90, boleto:107.90},
    {id:'B2', vel:550, label:'550 Mega + Chip 20GB', pix:102.90, boleto:112.90},
    {id:'B3', vel:800, label:'800 Mega + Vero Video Esportes + YouTube Premium + Chip 30GB', pix:129.90, boleto:139.90},
    {id:'B4', vel:800, label:'800 Mega + Globoplay + Chip 20GB', pix:139.90, boleto:149.90},
    {id:'B5', vel:800, label:'800 Mega + Disney + ESPN + Chip 20GB', pix:139.90, boleto:149.90},
    {id:'B6', vel:800, label:'800 Mega + Disney + HBO Max + Chip 30GB', pix:149.90, boleto:159.90},
    {id:'B7', vel:800, label:'800 Mega + Globoplay + HBO Max + Chip 60GB', pix:149.90, boleto:159.90},
    {id:'B8', vel:800, label:'800 Mega + Prime + Apple TV + Chip 30GB', pix:149.90, boleto:159.90},
    {id:'B9', vel:800, label:'800 Mega Premium (Prime + AppleTV + HBO + Globoplay + Chip 60GB)', pix:199.90, boleto:209.90},
  ]
};

const grupo = GRUPO_POR_CIDADE[cidadeNorm] || 'B';
const planos = PLANOS[grupo];

let mensagem = '';
try { mensagem = $('Entrada').first().json.mensagem || ''; } catch(e) {}
mensagem = String(mensagem).trim().toLowerCase();

let planoMatched = null;

// Tentativa 1: numero direto (1-9)
const numMatch = mensagem.match(/^\\s*(\\d+)\\s*$/);
if (numMatch) {
  const idx = parseInt(numMatch[1], 10) - 1;
  if (idx >= 0 && idx < planos.length) {
    planoMatched = planos[idx];
  }
}

// Tentativa 2: velocidade exata ("550" ou "800") — so vale se houver UM unico plano daquela velocidade
if (!planoMatched) {
  if (/\\b550\\b/.test(mensagem) && !/\\b800\\b/.test(mensagem)) {
    const cands = planos.filter(p => p.vel === 550);
    if (cands.length === 1) planoMatched = cands[0];
  } else if (/\\b800\\b/.test(mensagem) && !/\\b550\\b/.test(mensagem)) {
    const cands = planos.filter(p => p.vel === 800);
    if (cands.length === 1) planoMatched = cands[0];
  }
}

return [{ json: {
  cidade: cidade,
  grupo: grupo,
  planos: planos,
  catalogo_json: JSON.stringify(planos),
  plano_match_id: planoMatched ? planoMatched.id : null,
  plano_match_label: planoMatched ? planoMatched.label : null,
  camada1_ok: !!planoMatched,
}}];'''

NODES_NEW = [
    # GerarCatalogoPlanos — apos Atendido? true, antes de Step Aguarda CEP
    {
        "parameters": {"jsCode": CATALOGO_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [820, -800],
        "id": "gerar-catalogo",
        "name": "GerarCatalogoPlanos",
    },
    # ValidarEscolhaPlano — Camada 1 na aguarda_plano
    {
        "parameters": {"jsCode": VALIDAR_ESCOLHA_PLANO_CODE},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-280, 600],
        "id": "validar-escolha-plano",
        "name": "ValidarEscolhaPlano",
    },
    # Plano Valido?
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": "pv-1",
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
        "position": [-100, 600],
        "id": "plano-valido",
        "name": "Plano Valido?",
    },
    # Contexto Plano
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "cp1", "name": "tipo", "value": "plano", "type": "string"},
                    {"id": "cp2", "name": "pergunta", "value": "Qual plano te interessa?", "type": "string"},
                    {"id": "cp3", "name": "resposta",
                     "value": "={{ $node['Entrada'].json.mensagem }}", "type": "string"},
                    {"id": "cp4", "name": "contexto",
                     "value": "=Catalogo disponivel: {{ $node['ValidarEscolhaPlano'].json.catalogo_json }}. Cliente deve escolher UM plano. Match no catalogo retorna o id em formattedValue (ex: 'A4', 'B7'). Se ambiguo, retorna lista no errorMessage.",
                     "type": "string"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [100, 600],
        "id": "contexto-plano",
        "name": "Contexto Plano",
    },
    # Step Reasking Plano
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "srp1", "name": "resposta_bot",
                     "value": "={{ $node['ResultadoIA'].json.response.errorMessage || 'Nao reconheci qual plano. Pode mandar o numero da lista que mandei?' }}",
                     "type": "string"},
                    {"id": "srp2", "name": "proximo_nodo", "value": "aguarda_plano", "type": "string"},
                    {"id": "srp3", "name": "novas_vars",
                     "value": "={{ $node['Load Session'].json.dados }}", "type": "object"},
                    {"id": "srp4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [300, 750],
        "id": "step-reasking-plano",
        "name": "Step Reasking Plano",
    },
    # Step Aguarda Plano (via IA) — usa formattedValue=plano_id, lookup label
    {
        "parameters": {
            "assignments": {
                "assignments": [
                    {"id": "sapi1", "name": "resposta_bot",
                     "value": "=Otima escolha! Pra fechar, me passa seu email, por favor?",
                     "type": "string"},
                    {"id": "sapi2", "name": "proximo_nodo", "value": "aguarda_email", "type": "string"},
                    {"id": "sapi3", "name": "novas_vars",
                     "value": ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                               "{ plano_id: $node['ResultadoIA'].json.response.formattedValue, "
                               "  plano_interesse: $node['ResultadoIA'].json.response.formattedValue }) }}"),
                     "type": "object"},
                    {"id": "sapi4", "name": "deve_enviar_hubtrix", "value": "=false", "type": "boolean"},
                ]
            },
            "options": {},
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [300, 600],
        "id": "step-aguarda-plano-via-ia",
        "name": "Step Aguarda Plano (via IA)",
    },
]

# GET workflow
r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'ValidarEscolhaPlano' in existing:
    print('ValidarEscolhaPlano ja existe. Abortando (idempotencia).')
    sys.exit(0)

wf['nodes'].extend(NODES_NEW)

# Atualiza Step Aguarda CEP pra usar a lista_formatada na resposta_bot
for n in wf['nodes']:
    if n.get('name') == 'Step Aguarda CEP':
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'resposta_bot':
                a['value'] = ("=Perfeito! 😊 Em {{ $node['HTTP ViaCEP'].json.localidade }} a Vero tem:\n\n"
                              "{{ $node['GerarCatalogoPlanos'].json.lista_formatada }}\n\n"
                              "Qual te chama mais? Pode mandar o numero ou descrever.")
                print('Step Aguarda CEP resposta_bot atualizada com lista de planos')
                break
        break

# Atualiza Step Aguarda Plano (existente) pra salvar plano_id quando vem da Camada 1
for n in wf['nodes']:
    if n.get('name') == 'Step Aguarda Plano':
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'novas_vars':
                a['value'] = ("={{ Object.assign({}, $node['Load Session'].json.dados, "
                              "{ plano_id: $node['ValidarEscolhaPlano'].json.plano_match_id, "
                              "  plano_interesse: $node['ValidarEscolhaPlano'].json.plano_match_label }) }}")
                print('Step Aguarda Plano novas_vars: agora salva plano_id + plano_interesse com label completa')
                break
        break

conns = wf['connections']

# 1. Atendido? true (out 0) atual: vai pra Step Aguarda CEP. Inserir GerarCatalogoPlanos entre eles.
at = conns.get('Atendido?', {}).get('main', [])
if len(at) >= 1 and at[0]:
    print(f'Atendido? out0 atual: {at[0]}')
    at[0] = [{'node': 'GerarCatalogoPlanos', 'type': 'main', 'index': 0}]
    conns['GerarCatalogoPlanos'] = {'main': [[{'node': 'Step Aguarda CEP', 'type': 'main', 'index': 0}]]}
    print('Atendido? -> GerarCatalogoPlanos -> Step Aguarda CEP')

# 2. Por Nodo Atual [aguarda_plano] atual: vai pra Step Aguarda Plano. Inserir ValidarEscolhaPlano antes.
switch_outs = conns.get('Por Nodo Atual', {}).get('main', [])
out_idx_plano = None
for i, outs in enumerate(switch_outs):
    for tgt in (outs or []):
        if tgt.get('node') == 'Step Aguarda Plano':
            out_idx_plano = i
            break
    if out_idx_plano is not None:
        break
print(f'Por Nodo Atual output pra aguarda_plano: index={out_idx_plano}')
if out_idx_plano is not None:
    switch_outs[out_idx_plano] = [{'node': 'ValidarEscolhaPlano', 'type': 'main', 'index': 0}]

# Pipeline plano:
conns['ValidarEscolhaPlano'] = {'main': [[{'node': 'Plano Valido?', 'type': 'main', 'index': 0}]]}
conns['Plano Valido?'] = {
    'main': [
        [{'node': 'Step Aguarda Plano', 'type': 'main', 'index': 0}],   # true (Camada 1 OK)
        [{'node': 'Contexto Plano', 'type': 'main', 'index': 0}],       # false -> Camada 2
    ]
}
conns['Contexto Plano'] = {'main': [[{'node': 'IA Validator Universal', 'type': 'main', 'index': 0}]]}
conns['Step Reasking Plano'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
conns['Step Aguarda Plano (via IA)'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}

# 3. Adicionar branches plano nos Routers IA Tipo / Erro
for router_name, success_target, error_target in [
    ('Router IA Tipo', 'Step Aguarda Plano (via IA)', None),
    ('Router IA Tipo Erro', None, 'Step Reasking Plano'),
]:
    if router_name not in [n['name'] for n in wf['nodes']]:
        continue
    for n in wf['nodes']:
        if n['name'] == router_name:
            # Adicionar rule 'plano'
            new_rule = {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                    "conditions": [{
                        "id": f"r-plano-{router_name[-3:]}",
                        "leftValue": ("={{ (() => { "
                                      "try { return $('Contexto Email').first().json.tipo; } catch(e) {} "
                                      "try { return $('Contexto CEP').first().json.tipo; } catch(e) {} "
                                      "try { return $('Contexto Plano').first().json.tipo; } catch(e) {} "
                                      "return ''; "
                                      "})() }}"),
                        "rightValue": "plano",
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                    "combinator": "and",
                },
                "renameOutput": True,
                "outputKey": "plano",
            }
            # Atualiza todas as conditions ja existentes pra incluir Contexto Plano no lookup
            for rule in n['parameters']['rules']['values']:
                for c in rule['conditions']['conditions']:
                    c['leftValue'] = ("={{ (() => { "
                                      "try { return $('Contexto Email').first().json.tipo; } catch(e) {} "
                                      "try { return $('Contexto CEP').first().json.tipo; } catch(e) {} "
                                      "try { return $('Contexto Plano').first().json.tipo; } catch(e) {} "
                                      "return ''; "
                                      "})() }}")
            n['parameters']['rules']['values'].append(new_rule)
            print(f'{router_name}: adicionada regra plano + atualizadas expressions')

# Adicionar saidas dos Routers pra plano
# Router IA Tipo: 3a saida (plano) -> Step Aguarda Plano (via IA)
conns['Router IA Tipo'] = {
    'main': [
        [{'node': 'Step Aguarda Email (via IA)', 'type': 'main', 'index': 0}],   # email
        [{'node': 'CEP Resolvido IA', 'type': 'main', 'index': 0}],              # cep
        [{'node': 'Step Aguarda Plano (via IA)', 'type': 'main', 'index': 0}],   # plano (NOVO)
        [{'node': 'Step Aguarda Email (via IA)', 'type': 'main', 'index': 0}],   # fallback
    ]
}
conns['Router IA Tipo Erro'] = {
    'main': [
        [{'node': 'Step Reasking Email (via IA)', 'type': 'main', 'index': 0}],   # email
        [{'node': 'Step Reasking CEP (via IA)', 'type': 'main', 'index': 0}],     # cep
        [{'node': 'Step Reasking Plano', 'type': 'main', 'index': 0}],            # plano (NOVO)
        [{'node': 'Step Reasking Email (via IA)', 'type': 'main', 'index': 0}],   # fallback
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
print('\nValidador PLANO implementado com cascata completa.')
print('\nTopologia aguarda_plano:')
print('  Por Nodo Atual [aguarda_plano] -> ValidarEscolhaPlano -> Plano Valido?')
print('    true  -> Step Aguarda Plano (Camada 1: numero/velocidade)')
print('    false -> Contexto Plano -> IA Validator -> ResultadoIA -> IA OK?')
print('               true  -> Router IA Tipo [plano] -> Step Aguarda Plano (via IA)')
print('               false -> Router IA Tipo Erro [plano] -> Step Reasking Plano')
