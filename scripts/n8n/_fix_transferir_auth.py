"""Corrige a auth do no 'Transferir Fila' no fluxo de follow-up: usa o header
X-N8N-Webhook-Secret (copiado de um no Hubtrix do orquestrador), nao a cred uazapi.
NAO ecoa o valor do segredo."""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

n = N8N()
# pega o valor do X-N8N-Webhook-Secret de um no Hubtrix do orquestrador
orq = n.get_workflow('Df1BgcXdg3HAUZwf')
secret = None
for nd in orq['nodes']:
    if not nd.get('type','').endswith('httpRequest'):
        continue
    url = nd.get('parameters',{}).get('url','') or ''
    if 'hubtrix' not in url.lower():
        continue
    for h in nd.get('parameters',{}).get('headerParameters',{}).get('parameters',[]) or []:
        if (h.get('name') or '').lower() == 'x-n8n-webhook-secret' and h.get('value'):
            secret = h['value']; break
    if secret: break
assert secret, 'X-N8N-Webhook-Secret nao achado em no Hubtrix do orquestrador'
print('secret X-N8N-Webhook-Secret: encontrado (oculto), len=', len(secret))

WID = 'tYckyds4TqPpFOWd'
w = n.get_workflow(WID); nodes = w['nodes']
tf = next(nd for nd in nodes if nd['name'] == 'Transferir Fila')
p = tf['parameters']
p.pop('authentication', None); p.pop('genericAuthType', None)
p['sendHeaders'] = True
p['headerParameters'] = {'parameters': [
    {'name': 'X-N8N-Webhook-Secret', 'value': secret},
    {'name': 'Content-Type', 'value': 'application/json'},
]}
tf.pop('credentials', None)  # tira a cred uazapi errada
print('Transferir Fila: auth trocada p/ header X-N8N-Webhook-Secret, cred removida')

so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes, 'connections': w['connections'], 'settings': sl})
print('PUT ok. (INATIVO)')

w2 = n.get_workflow(WID)
tf2 = next(nd for nd in w2['nodes'] if nd['name'] == 'Transferir Fila')
hdrs = [h['name'] for h in tf2['parameters'].get('headerParameters',{}).get('parameters',[])]
print('headers agora:', hdrs, '| credentials:', tf2.get('credentials'))
