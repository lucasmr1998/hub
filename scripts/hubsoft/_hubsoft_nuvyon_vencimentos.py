"""READ-ONLY: lista os vencimentos marcados na HubSoft da Nuvyon (artelecom).
GET /api/v1/integracao/configuracao/vencimento. Creds em .env.nuvyon_hubsoft.
Destino: https://api.artelecom.hubsoft.com.br (tenant Nuvyon).
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
import requests

env = {}
for l in (Path(__file__).resolve().parents[1] / '.env.nuvyon_hubsoft').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
BASE = env['HUBSOFT_HOST'].rstrip('/')

tok = requests.post(f'{BASE}/oauth/token', json={
    'client_id': env['HUBSOFT_CLIENT_ID'], 'client_secret': env['HUBSOFT_CLIENT_SECRET'],
    'username': env['HUBSOFT_USERNAME'], 'password': env['HUBSOFT_PASSWORD'],
    'grant_type': env['HUBSOFT_GRANT_TYPE'],
}, timeout=30)
tok.raise_for_status()
access = tok.json().get('access_token', '')
print('Token OK' if access else 'SEM TOKEN')

r = requests.get(f'{BASE}/api/v1/integracao/configuracao/vencimento',
                 headers={'Authorization': f'Bearer {access}', 'Accept': 'application/json'},
                 timeout=30)
r.raise_for_status()
data = r.json()
venc = data.get('vencimentos') or data.get('dia_vencimento') or []
print(f'\nVencimentos na HubSoft Nuvyon: {len(venc)}')
print('chaves do 1o registro:', list(venc[0].keys()) if venc else '-')
for v in venc:
    print('  ' + json.dumps(v, ensure_ascii=False))
