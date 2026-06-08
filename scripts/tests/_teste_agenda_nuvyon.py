"""READ-ONLY: testa horarios_disponiveis_agenda na artelecom (Nuvyon) pra achar uma
agenda valida e validar o contrato que o consultar_agenda do Hubtrix consome."""
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
B = env['HUBSOFT_HOST'].rstrip('/')
tok = requests.post(f'{B}/oauth/token', json={
    'client_id': env['HUBSOFT_CLIENT_ID'], 'client_secret': env['HUBSOFT_CLIENT_SECRET'],
    'username': env['HUBSOFT_USERNAME'], 'password': env['HUBSOFT_PASSWORD'],
    'grant_type': env['HUBSOFT_GRANT_TYPE']}, timeout=30)
H = {'Authorization': f"Bearer {tok.json().get('access_token','')}", 'Accept': 'application/json'}
print('token:', 'OK' if 'access_token' in tok.json() else 'FALHOU')

EP = f'{B}/api/v1/integracao/ordem_servico/horarios_disponiveis_agenda'
for aid in (1, 2, 3, 4, 5, 6, 10, 154):
    r = requests.get(EP, headers=H, params={'id_agenda_ordem_servico': aid,
                     'data_inicio': '2026-06-01', 'dias': 7}, timeout=30)
    try:
        d = r.json()
    except Exception:
        print(f'  id_agenda {aid}: HTTP {r.status_code} (nao-json)'); continue
    st = d.get('status'); ag = d.get('agenda')
    datas = (d.get('horarios') or {}).get('datas') or {}
    msg = d.get('msg', '')
    if st == 'success':
        # conta horarios totais
        tot = sum(len((v.get('horarios') or {})) for v in datas.values())
        print(f'  id_agenda {aid}: OK agenda={ag!r} datas={list(datas.keys())[:3]} horarios_total={tot}')
    else:
        print(f'  id_agenda {aid}: {st} - {msg[:80]}')
