"""READ-ONLY: dumpa tipo_atendimento e tipo_ordem_servico da artelecom (id + descricao)
pra validar 535/702 e achar os IDs corretos de INSTALACAO."""
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
    'grant_type': env['HUBSOFT_GRANT_TYPE']}, timeout=30)
H = {'Authorization': f"Bearer {tok.json().get('access_token','')}", 'Accept': 'application/json'}

for ep in ('/api/v1/integracao/configuracao/tipo_atendimento',
           '/api/v1/integracao/configuracao/tipo_ordem_servico'):
    r = requests.get(f'{BASE}{ep}', headers=H, timeout=25)
    data = r.json()
    print(f'\n==== {ep} ====')
    # acha a lista (primeira chave que for lista)
    lista = None
    for k, v in (data.items() if isinstance(data, dict) else []):
        if isinstance(v, list):
            lista = v; print('chave lista:', k, '| total:', len(v)); break
    if lista is None:
        print(json.dumps(data, ensure_ascii=False)[:300]); continue
    print('chaves do item:', list(lista[0].keys()) if lista else '-')
    for it in lista:
        idv = it.get('id_tipo_atendimento') or it.get('id_tipo_ordem_servico') or it.get('id')
        desc = it.get('descricao') or it.get('nome') or it.get('tipo') or ''
        print(f'  id={idv} | {desc}')
