"""Testa o que o FLUXO faz pra Mococa: ViaCEP(CEP) -> viabilidade modo ENDERECO.
Mostra se o modo endereco acha o projeto (ou se o geocode erra)."""
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

CEPS = ['13730000', '13730150', '13730340']  # alguns CEPs de Mococa/SP
tok = requests.post(f'{BASE}/oauth/token', json={
    'client_id': env['HUBSOFT_CLIENT_ID'], 'client_secret': env['HUBSOFT_CLIENT_SECRET'],
    'username': env['HUBSOFT_USERNAME'], 'password': env['HUBSOFT_PASSWORD'],
    'grant_type': env['HUBSOFT_GRANT_TYPE']}, timeout=30)
access = tok.json().get('access_token', '')
print('token:', 'OK' if access else 'FALHOU')

for cep in CEPS:
    vc = requests.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=20).json()
    if vc.get('erro'):
        print(f'\nCEP {cep}: ViaCEP nao achou'); continue
    body = {'tipo_busca': 'endereco', 'raio': 1000, 'detalhar_portas': False,
            'endereco': {'numero': 'S/N', 'endereco': vc.get('logradouro',''),
                         'bairro': vc.get('bairro',''), 'cidade': vc.get('localidade',''),
                         'estado': vc.get('uf','')}}
    r = requests.post(f'{BASE}/api/v1/integracao/mapeamento/viabilidade/consultar',
                      headers={'Authorization': f'Bearer {access}', 'Content-Type': 'application/json'},
                      json=body, timeout=45)
    res = (r.json() or {}).get('resultado', {})
    proj = res.get('projetos')
    achou = isinstance(proj, list) and len(proj) > 0
    print(f"\nCEP {cep} ({vc.get('logradouro','')}, {vc.get('bairro','')}, {vc.get('localidade')}/{vc.get('uf')})")
    print(f"  -> projeto encontrado: {achou}  | projetos={proj if not achou else len(proj)}")
