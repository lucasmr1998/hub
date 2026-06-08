"""Troca empresa MEGALINK->NUVYON (uppercase, so os 2 nos de empresa, nao
mexe na instancia Evolution 'Megalink - MCV') e ativa o workflow Nuvyon.
Backup antes.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'q60Omy70nfmGgBQt'
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_nuvyon_flow_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

# substitui 'MEGALINK' (uppercase) -> 'NUVYON' nos parametros dos nos
afetados = []
for nd in nodes:
    raw = json.dumps(nd.get('parameters', {}), ensure_ascii=False)
    if 'MEGALINK' in raw:
        novo = json.loads(raw.replace('MEGALINK', 'NUVYON'))
        nd['parameters'] = novo
        afetados.append(nd['name'])
print('Nos com empresa corrigida:', afetados)

so = w.get('settings', {})
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes,
    'connections': w['connections'], 'settings': sl})
print('PUT ok (empresa corrigida).')

# ativa
try:
    r = n.activate_workflow(WID)
    print('Ativado:', r.get('active') if isinstance(r, dict) else r)
except Exception as e:
    print('Falha ao ativar:', e)

# verifica
w2 = n.get_workflow(WID)
print('active agora:', w2.get('active'))
# confirma empresa
import re
mega = sum(json.dumps(nd.get('parameters',{}),ensure_ascii=False).count('MEGALINK') for nd in w2['nodes'])
nuv = sum(json.dumps(nd.get('parameters',{}),ensure_ascii=False).count('NUVYON') for nd in w2['nodes'])
print(f'MEGALINK restante (uppercase): {mega} | NUVYON: {nuv}')
