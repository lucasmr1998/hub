"""Fix Bug B: contador muito_erro do DetectarPedidoHumano dispara handoff
antes de validar a mensagem atual. Cliente que erra 2x e acerta na 3a era
chutado pra humano sem o bot tentar a resposta valida.

Fix: avaliar muito_erro sobre a contagem ANTERIOR (pre-incremento), dando
a mensagem corrente a chance de ser validada. So desiste se ja falhou 3x.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'Df1BgcXdg3HAUZwf'
NODE = 'DetectarPedidoHumano'

ANTIGO = """const tentativas = mudou_de_estado ? 1 : ((dados[tentativas_key] || 0) + 1);
const muito_erro = tentativas >= 3;"""

NOVO = """const tentativas_anteriores = mudou_de_estado ? 0 : (dados[tentativas_key] || 0);
const tentativas = tentativas_anteriores + 1;
// Avalia sobre a contagem ANTERIOR: a mensagem atual sempre tem chance de
// ser validada. So vai pra humano se ja falhou 3x antes desta mensagem.
const muito_erro = tentativas_anteriores >= 3;"""

n = N8N()
w = n.get_workflow(WID)

# Backup
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_orquestrador_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

nodes = w['nodes']
alvo = next((nd for nd in nodes if nd['name'] == NODE), None)
if not alvo:
    sys.exit(f'Node {NODE} nao encontrado')

code = alvo['parameters'].get('jsCode', '')
if ANTIGO not in code:
    if 'tentativas_anteriores' in code:
        print('Fix ja aplicado (tentativas_anteriores presente). Nada a fazer.')
        sys.exit(0)
    print('ERRO: trecho antigo nao encontrado. Trecho atual relevante:')
    for ln in code.split(chr(10)):
        if 'tentativas' in ln or 'muito_erro' in ln:
            print('   ', ln)
    sys.exit(1)

code_novo = code.replace(ANTIGO, NOVO)
alvo['parameters']['jsCode'] = code_novo
print('Trecho substituido. Preview do novo:')
for ln in code_novo.split(chr(10)):
    if 'tentativas' in ln or 'muito_erro' in ln:
        print('   ', ln)

# PUT limpo
settings_orig = w.get('settings', {})
settings_limpo = {k: settings_orig[k] for k in (
    'executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in settings_orig}
payload = {'name': w['name'], 'nodes': nodes,
           'connections': w['connections'], 'settings': settings_limpo}
print('\nEnviando PUT...')
res = n.update_workflow(WID, payload)
print('OK. Workflow atualizado. nodes:', len(res.get('nodes', nodes)))
