"""Teste viabilidade por coordenadas (centro de Teresina/PI) na HubSoft artelecom.
Raio grande pra detectar se ha projetos Nuvyon na cidade. Sem secrets.
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
import requests

env = {}
for l in Path('.env.nuvyon_hubsoft').read_text(encoding='utf-8').splitlines():
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
print('Token:', 'OK' if access else 'FALHOU')

# centro de Teresina/PI
for raio in (1000, 5000):
    payload = {'tipo_busca': 'coordenadas', 'raio': raio,
               'latitude': -5.0892, 'longitude': -42.8019, 'detalhar_portas': True}
    r = requests.post(f'{BASE}/api/v1/integracao/mapeamento/viabilidade/consultar',
                      headers={'Authorization': f'Bearer {access}', 'Content-Type': 'application/json'},
                      json=payload, timeout=45)
    print(f'\n=== raio {raio}m  -> HTTP {r.status_code} ===')
    try:
        data = r.json()
    except Exception:
        print('resp:', r.text[:200]); continue
    res = data.get('resultado') or {}
    print('status:', data.get('status'), '| msg:', data.get('msg', ''))
    print(json.dumps(res, ensure_ascii=False, indent=1)[:1800])
