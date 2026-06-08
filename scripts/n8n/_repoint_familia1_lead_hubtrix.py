"""Familia 1: repoint dos nos de lead/CRM do fluxo Nuvyon Megalink->Hubtrix.
- URL: *.megalinkpiaui.com.br -> app.hubtrix.com.br (mesmo path)
- Auth: credencial httpHeaderAuth 'Hubtrix Nuvyon API' (Bearer token nuvyon)
Backup antes. Idempotente.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'q60Omy70nfmGgBQt'
CRED_ID = 'KIwC6D7r4xObkYha'
CRED_NAME = 'Hubtrix Nuvyon API'

n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_nuvyon_flow_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

alvos = []
for nd in nodes:
    if not nd.get('type', '').endswith('httpRequest'):
        continue
    url = nd.get('parameters', {}).get('url', '') or ''
    if 'megalinkpiaui.com.br' in url:
        alvos.append(nd)

print(f'\nNos Familia 1 (megalinkpiaui): {len(alvos)}')
for nd in alvos:
    p = nd['parameters']
    antiga = p['url']
    nova = antiga.replace('megacadastro.megalinkpiaui.com.br', 'app.hubtrix.com.br') \
                 .replace('robovendas.megalinkpiaui.com.br', 'app.hubtrix.com.br')
    p['url'] = nova
    # auth
    p['authentication'] = 'genericCredentialType'
    p['genericAuthType'] = 'httpHeaderAuth'
    nd['credentials'] = {'httpHeaderAuth': {'id': CRED_ID, 'name': CRED_NAME}}
    nome_nd = nd['name']
    print(f'  {nome_nd}: {antiga} -> {nova}  [+cred]')

if not alvos:
    print('Nada a repontar.'); sys.exit(0)

so = w.get('settings', {})
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
res = n.update_workflow(WID, {'name': w['name'], 'nodes': nodes,
    'connections': w['connections'], 'settings': sl})
print('\nPUT ok. nodes:', len(res.get('nodes', nodes)))

# verifica
w2 = n.get_workflow(WID)
for nd in w2['nodes']:
    if nd.get('type','').endswith('httpRequest'):
        u = nd.get('parameters',{}).get('url','') or ''
        if 'app.hubtrix.com.br/api/leads' in u:
            cred = nd.get('credentials',{}).get('httpHeaderAuth',{}).get('name')
            nn = nd['name']
            print(f'  OK {nn}: {u} cred={cred}')
