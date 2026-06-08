"""Familia 2: repoint dos nos HubSoft do fluxo Nuvyon Megalink->artelecom.
- URL: api.megalinktelecom.hubsoft.com.br -> api.artelecom.hubsoft.com.br
- TokenHubsoft*: jsonBody com creds Nuvyon (lidas de .env.nuvyon_hubsoft, gitignored)
Backup antes. Nao ecoa secrets.
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from _n8n_api import N8N

# creds do arquivo gitignored
env = {}
for l in (Path(__file__).resolve().parents[1] / '.env.nuvyon_hubsoft').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()

token_body = json.dumps({
    'client_id': env['HUBSOFT_CLIENT_ID'],
    'client_secret': env['HUBSOFT_CLIENT_SECRET'],
    'username': env['HUBSOFT_USERNAME'],
    'password': env['HUBSOFT_PASSWORD'],
    'grant_type': env['HUBSOFT_GRANT_TYPE'],
}, ensure_ascii=False)

WID = 'q60Omy70nfmGgBQt'
OLD = 'api.megalinktelecom.hubsoft.com.br'
NEW = 'api.artelecom.hubsoft.com.br'

n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_nuvyon_flow_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

n_url, n_cred = 0, 0
for nd in nodes:
    p = nd.get('parameters', {})
    url = p.get('url', '') or ''
    if OLD in url:
        p['url'] = url.replace(OLD, NEW)
        n_url += 1
        # se for o no de token, troca o jsonBody pelas creds Nuvyon
        if nd['name'].startswith('TokenHubsoft'):
            p['jsonBody'] = token_body
            n_cred += 1
        print(f'  {nd["name"]}: url->artelecom' + ('  [+creds]' if nd['name'].startswith('TokenHubsoft') else ''))

print(f'\nURLs repointadas: {n_url} | TokenHubsoft com creds Nuvyon: {n_cred}')
if not n_url:
    print('Nada a repontar.'); sys.exit(0)

so = w.get('settings', {})
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
res = n.update_workflow(WID, {'name': w['name'], 'nodes': nodes,
    'connections': w['connections'], 'settings': sl})
print('PUT ok. nodes:', len(res.get('nodes', nodes)))

# verifica (sem secrets)
w2 = n.get_workflow(WID)
restantes = [nd['name'] for nd in w2['nodes'] if OLD in (nd.get('parameters', {}).get('url', '') or '')]
print('Nos ainda com megalinktelecom:', restantes or 'nenhum')
