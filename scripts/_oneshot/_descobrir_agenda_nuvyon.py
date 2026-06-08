"""READ-ONLY: descobre id_agenda_ordem_servico da Nuvyon (artelecom) a partir dos
dados reais — tecnicos (pivot.id_agenda_ordem_servico) e OSes existentes."""
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

# 1. tecnicos -> agendas (pivot)
r = requests.get(f'{B}/api/v1/integracao/configuracao/tecnico', headers=H, timeout=30)
data = r.json()
tecnicos = data.get('tecnicos') or data.get('usuarios') or (data if isinstance(data, list) else [])
print(f'/configuracao/tecnico: HTTP {r.status_code} | tecnicos={len(tecnicos)}')
agendas = {}  # id_agenda -> nomes de tecnicos
for t in tecnicos[:50]:
    nome = t.get('name') or t.get('nome') or '?'
    # procura pivots/agendas no tecnico
    raw = json.dumps(t, ensure_ascii=False)
    for m in re.findall(r'"id_agenda_ordem_servico"\s*:\s*(\d+)', raw):
        agendas.setdefault(int(m), set()).add(nome)
    # estrutura comum: t['agendas'] ou t['pivot']
print('\nAgendas encontradas (id -> tecnicos):')
if agendas:
    for aid, tecs in sorted(agendas.items()):
        print(f'  id_agenda_ordem_servico={aid}  tecnicos={sorted(tecs)[:5]}')
else:
    print('  nenhum id_agenda nos tecnicos. Chaves do 1o tecnico:', list(tecnicos[0].keys()) if tecnicos else '-')

# 2. tenta horarios em cada agenda achada
for aid in sorted(agendas):
    rr = requests.get(f'{B}/api/v1/integracao/ordem_servico/horarios_disponiveis_agenda',
                      headers=H, params={'id_agenda_ordem_servico': aid, 'data_inicio': '2026-06-01', 'dias': 7}, timeout=30)
    dd = rr.json()
    if dd.get('status') == 'success':
        datas = (dd.get('horarios') or {}).get('datas') or {}
        tot = sum(len((v.get('horarios') or {})) for v in datas.values())
        print(f"\n>>> AGENDA {aid} OK: nome={dd.get('agenda')!r} datas={list(datas.keys())[:4]} horarios={tot}")
