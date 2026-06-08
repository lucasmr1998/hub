"""READ-ONLY: lista OSes existentes da Nuvyon (artelecom) e procura referencia de agenda."""
import sys, json, re
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
import requests

env = {}
for l in Path('.env.nuvyon_hubsoft').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
B = env['HUBSOFT_HOST'].rstrip('/')
tok = requests.post(f'{B}/oauth/token', json={
    'client_id': env['HUBSOFT_CLIENT_ID'], 'client_secret': env['HUBSOFT_CLIENT_SECRET'],
    'username': env['HUBSOFT_USERNAME'], 'password': env['HUBSOFT_PASSWORD'],
    'grant_type': env['HUBSOFT_GRANT_TYPE']}, timeout=30)
H = {'Authorization': f"Bearer {tok.json().get('access_token','')}", 'Accept': 'application/json'}

r = requests.get(f'{B}/api/v1/integracao/ordem_servico/todos', headers=H,
                 params={'pagina': 0, 'itens_por_pagina': 15, 'data_inicio': '2026-04-01', 'data_fim': '2026-06-30'},
                 timeout=40)
data = r.json()
oss = data.get('ordens_servico') or []
print(f'/ordem_servico/todos: HTTP {r.status_code} | OSes={len(oss)}')
if oss:
    print('chaves de uma OS:', list(oss[0].keys()))
# procura qualquer referencia a agenda em todas as OSes
raw = json.dumps(data, ensure_ascii=False)
for m in set(re.findall(r'"id_agenda_ordem_servico"\s*:\s*"?(\d+)"?', raw)):
    print('  id_agenda_ordem_servico achado em OS:', m)
print('\nAgenda de cada OS (campo agenda_ordem_servico):')
agendas = {}
for o in oss:
    ag = o.get('agenda_ordem_servico')
    if isinstance(ag, dict):
        aid = ag.get('id_agenda_ordem_servico') or ag.get('id')
        nome = ag.get('descricao') or ag.get('nome')
        if aid is not None:
            agendas[aid] = nome
        print(f"  OS {o.get('id_ordem_servico')} ({o.get('tipo_ordem_servico') or o.get('tipo')}): agenda id={aid} nome={nome!r}")
    else:
        print(f"  OS {o.get('id_ordem_servico')} ({o.get('tipo')}): agenda_ordem_servico={ag!r}")
print('\nAGENDAS distintas encontradas:', {k: v for k, v in agendas.items()})
