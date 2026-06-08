"""READ-ONLY: sonda a HubSoft artelecom por catalogos de config (tipo_atendimento,
tipo_ordem_servico, status, vendedor) pra validar os IDs hardcoded do fluxo:
535 (tipo atendimento), 702 (tipo OS), 1 (status atendimento), 1618 (responsavel).
So GET. Reporta status de cada endpoint e se o ID aparece."""
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
access = tok.json().get('access_token', '')
print('token:', 'OK' if access else 'FALHOU')
H = {'Authorization': f'Bearer {access}', 'Accept': 'application/json'}

candidatos = [
    '/api/v1/integracao/configuracao/tipo_atendimento',
    '/api/v1/integracao/configuracao/atendimento_tipo',
    '/api/v1/integracao/configuracao/tipo_ordem_servico',
    '/api/v1/integracao/configuracao/ordem_servico_tipo',
    '/api/v1/integracao/configuracao/atendimento_status',
    '/api/v1/integracao/configuracao/ordem_servico_status',
    '/api/v1/integracao/configuracao/usuario',
    '/api/v1/integracao/configuracao/vendedor',
    '/api/v1/integracao/configuracao/tecnico',
]
for ep in candidatos:
    try:
        r = requests.get(f'{BASE}{ep}', headers=H, timeout=25)
        body = r.text
        ok = r.status_code == 200
        achou = []
        if ok:
            for tid in ('535', '702', '"id":1', '1618'):
                if tid in body:
                    achou.append(tid)
        print(f'  {r.status_code}  {ep}  ' + (f'IDs presentes: {achou}; len={len(body)}' if ok else body[:90]))
    except Exception as e:
        print(f'  ERR  {ep}  {str(e)[:80]}')
