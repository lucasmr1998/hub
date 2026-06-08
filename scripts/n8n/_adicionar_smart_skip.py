"""
SmartSkip: detecta campos ja preenchidos no `novas_vars` e pula direto
pro proximo estado nao preenchido. Plugado entre TODOS os Steps e Save Session.

Logica:
  1. Recebe input do Step (resposta_bot, proximo_nodo, novas_vars, ...)
  2. Olha proximo_nodo pretendido pelo Step
  3. Pra cada estado a partir desse, verifica se o CAMPO esperado ja esta preenchido
  4. Se sim, pula pra proximo estado
  5. Se todos estiverem preenchidos, vai pra aguarda_confirmacao_final
  6. Retorna o mesmo objeto mas com proximo_nodo possivelmente alterado

Tambem ajusta resposta_bot se pulou: troca pra mensagem do estado pra qual pulou.
Pra simplicidade: nao mexe em resposta_bot por enquanto. Bot manda a resposta original
e no PROXIMO turno o cliente ja esta no estado pulado. (Acceptable trade-off.)

Atualizacao: pra melhor UX, troca a resposta_bot pra "ja temos esses dados, vamos pra X"
quando detectar skip.
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

SMART_SKIP_CODE = '''// SmartSkip — pula estados ja preenchidos
// Ordem dos estados + campo que cada um espera
const ORDEM = [
  {estado: 'aguarda_nome',             campo: 'nome'},
  {estado: 'aguarda_cep',              campo: 'cep'},
  // confirmacao_cep nao precisa skip (e sempre necessaria apos cep novo)
  {estado: 'aguarda_numero',           campo: 'numero'},
  {estado: 'aguarda_complemento',      campo: 'complemento', opcional: true},
  {estado: 'aguarda_plano',            campo: 'plano_id'},
  {estado: 'aguarda_cpf',              campo: 'cpf'},
  {estado: 'aguarda_data_nasc',        campo: 'data_nascimento'},
  {estado: 'aguarda_email',            campo: 'email'},
  {estado: 'aguarda_doc_rg_frente',    campo: 'doc_rg_frente_url'},
  {estado: 'aguarda_doc_rg_verso',     campo: 'doc_rg_verso_url'},
];

const item = $input.first().json;
const dados = item.novas_vars || {};
let proximo = item.proximo_nodo;

// Encontra index do estado pretendido
const idx = ORDEM.findIndex(o => o.estado === proximo);
if (idx === -1) {
  // Estado nao mapeado (concluido, aguarda_humano, aguarda_decisao_*, etc) — passa direto
  return [{ json: item }];
}

// Verifica se campos seguintes ja estao preenchidos. Avanca ate achar um sem dado.
let novo_estado = proximo;
let pulou = false;
for (let i = idx; i < ORDEM.length; i++) {
  const {estado, campo, opcional} = ORDEM[i];
  const valor = dados[campo];
  const preenchido = !!valor || (opcional && valor === '');
  if (!preenchido) {
    novo_estado = estado;
    break;
  }
  if (i === ORDEM.length - 1) {
    // Todos preenchidos
    novo_estado = 'aguarda_confirmacao_final';
    pulou = true;
  } else {
    pulou = true;
  }
}

const out = { ...item, proximo_nodo: novo_estado };
if (pulou && novo_estado !== proximo) {
  // Sobrescreve resposta_bot pra avisar do skip (UX)
  out.resposta_bot = `Ja tenho esses dados! Vamos pular pra proxima etapa... ${item.resposta_bot || ''}`.trim();
  out._smart_skip_aplicado = true;
  out._proximo_pretendido = proximo;
  out._proximo_real = novo_estado;
}
return [{ json: out }];'''

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
wf = r.json()

existing = {n['name'] for n in wf['nodes']}
if 'SmartSkip' in existing:
    print('Ja existe.')
    sys.exit(0)

wf['nodes'].append({
    "parameters": {"jsCode": SMART_SKIP_CODE},
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1850, 0],   # logo antes do Save Session
    "id": "smart-skip",
    "name": "SmartSkip",
})

# Reescrever todas conexoes que apontam pra Save Session pra apontarem pra SmartSkip
# E SmartSkip -> Save Session
conns = wf['connections']
redirected = 0
for src, ports in conns.items():
    for port_name, branches in ports.items():
        for branch in branches:
            for i, tgt in enumerate(branch):
                if tgt.get('node') == 'Save Session':
                    branch[i] = {'node': 'SmartSkip', 'type': 'main', 'index': 0}
                    redirected += 1

conns['SmartSkip'] = {'main': [[{'node': 'Save Session', 'type': 'main', 'index': 0}]]}
print(f'Redirecionadas {redirected} conexoes: Step X -> SmartSkip -> Save Session')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': conns, 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT {r.status_code}')
