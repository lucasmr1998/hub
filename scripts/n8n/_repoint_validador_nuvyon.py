"""Repoint 'so validador' da copia Nuvyon kIGvBSkGBUDpO2V4.
Troca o webhook path do QuestionValidator: 'atendimento-v2' -> 'nuvyion'.
Backup antes. PUT com settings filtrado. Nao ativa.
Destino: Matrix passa a bater em
  https://automation-n8n.v4riem.easypanel.host/webhook/nuvyion
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
OLD_PATH = 'atendimento-v2'
NEW_PATH = 'nuvyion'

n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_copia_nuvyon_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

changed = []
for nd in nodes:
    if nd.get('type', '').endswith('webhook'):
        p = nd.get('parameters', {})
        if p.get('path') == OLD_PATH:
            p['path'] = NEW_PATH
            changed.append(nd['name'])
print('Webhook path alterado em:', changed)
if not changed:
    print('Nada a alterar (path nao encontrado).'); sys.exit(1)

so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes,
    'connections': w['connections'], 'settings': sl})
print('PUT ok.')

# verifica
w2 = n.get_workflow(WID)
for nd in w2['nodes']:
    if nd.get('type', '').endswith('webhook') and nd.get('parameters', {}).get('path') == NEW_PATH:
        print(f'  OK: {nd["name"]} -> path={NEW_PATH!r}')
print(f'\nDestino final: https://automation-n8n.v4riem.easypanel.host/webhook/{NEW_PATH}')
