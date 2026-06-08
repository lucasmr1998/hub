"""Duplica o fluxo [Megalink] Matrix | Atendimento Fixo | 1.2 (PeEAQN6y5ihbzXWF).
Cria uma copia INATIVA com nome '... | 1.2 copy'. Copia fiel (mesmas creds/refs).
Backup do original antes. Nao ativa nada.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

SRC = 'PeEAQN6y5ihbzXWF'
n = N8N()
w = n.get_workflow(SRC)
print(f'Fonte: {w["name"]}  (nodes={len(w["nodes"])}, active={w.get("active")})')

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_megalink12_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup fonte:', bk)

# settings: API de create so aceita subconjunto
so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}

payload = {
    'name': f'{w["name"]} copy',
    'nodes': w['nodes'],
    'connections': w['connections'],
    'settings': sl,
}

res = n.create_workflow(payload)
print('\nCriado:')
print('  id    :', res.get('id'))
print('  name  :', res.get('name'))
print('  active:', res.get('active'))
print('  nodes :', len(res.get('nodes', [])))
