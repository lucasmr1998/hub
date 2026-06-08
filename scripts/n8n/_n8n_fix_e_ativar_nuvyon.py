"""Resolve o conflito de webhook da copia Nuvyon kIGvBSkGBUDpO2V4 e ativa.
- backup do estado atual
- CheckTypeWebhook path: '8a61fb9e-...-CheckType' -> 'nuvyion1-checktype' (unico)
- PUT (settings filtrado) e ativar
NAO mexe no QuestionValidator (nuvyion1) nem em creds.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
OLD = '8a61fb9e-5558-4d3f-ace7-2295df84de6e-CheckType'
NEW = 'nuvyion1-checktype'

n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
print(f'Alvo: {w["name"]}  active={w.get("active")}')

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_nuvyon_copia_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

ct = next(nd for nd in nodes if nd.get('name') == 'CheckTypeWebhook')
assert ct['parameters'].get('path') == OLD, ct['parameters'].get('path')
ct['parameters']['path'] = NEW
print(f'CheckTypeWebhook path: {OLD!r} -> {NEW!r}')

so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes,
    'connections': w['connections'], 'settings': sl})
print('PUT ok.')

print('\nAtivando...')
try:
    r = n.activate_workflow(WID)
    print('OK ->', r.get('active') if isinstance(r, dict) else r)
except Exception as e:
    print('FALHOU:', str(e)[:600])

w2 = n.get_workflow(WID)
print('active agora:', w2.get('active'))
print('webhooks:', {nd['name']: nd['parameters'].get('path')
                    for nd in w2['nodes'] if nd.get('type','').endswith('webhook')})
