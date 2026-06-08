"""Bate na HubSoft da Nuvyon (artelecom) e acha o id_servico dos planos.
Creds em .env.nuvyon_hubsoft (gitignored). Read-only (POST /oauth/token + GET catalogo).
Nao ecoa secrets.
Destino: https://api.artelecom.hubsoft.com.br  (tenant Nuvyon, conta hubtrix@nuvyon.com.br)
"""
import sys, re
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

# alvos: nome -> preco informado
ALVOS = [
    ('NUVYON - 300MB', 78.9),
    ('NUVYON - 300MB 2', 89.9),
    ('NUVYON - 400MB', 89.9),
    ('NUVYON - 500MB', 99.9),
    ('NUVYON - 600MB 1 (PROMOCIONAL)', 109.9),
    ('NUVYON - 600MB 11', 129.9),
    ('NUVYON - 800MB 2', 189.9),
]

def norm(s):
    return re.sub(r'\s+', ' ', str(s or '').strip().upper())

# 1. token
tok = requests.post(f'{BASE}/oauth/token', json={
    'client_id': env['HUBSOFT_CLIENT_ID'],
    'client_secret': env['HUBSOFT_CLIENT_SECRET'],
    'username': env['HUBSOFT_USERNAME'],
    'password': env['HUBSOFT_PASSWORD'],
    'grant_type': env['HUBSOFT_GRANT_TYPE'],
}, timeout=30)
tok.raise_for_status()
access = tok.json().get('access_token', '')
print('Token OK' if access else f'SEM TOKEN: {tok.text[:200]}')

# 2. catalogo de servicos
r = requests.get(f'{BASE}/api/v1/integracao/configuracao/servico',
                 headers={'Authorization': f'Bearer {access}', 'Accept': 'application/json'},
                 timeout=30)
r.raise_for_status()
servicos = r.json().get('servicos') or []
print(f'Servicos no catalogo: {len(servicos)}\n')

# indice por nome normalizado
idx = {}
for s in servicos:
    nome = s.get('descricao') or s.get('nome') or s.get('servico') or ''
    idx.setdefault(norm(nome), []).append(s)

def fmt(s):
    val = s.get('valor') or s.get('valor_servico') or s.get('preco') or ''
    return f"id_servico={s.get('id_servico')}  desc={s.get('descricao')!r}  valor={val}"

print('== MATCH dos alvos ==')
nao_achou = []
for nome, preco in ALVOS:
    achados = idx.get(norm(nome), [])
    if achados:
        for s in achados:
            print(f'  [{preco:>6}] {nome:35s} -> {fmt(s)}')
    else:
        nao_achou.append((nome, preco))
        print(f'  [{preco:>6}] {nome:35s} -> (sem match exato)')

if nao_achou:
    print('\n== CATALOGO COMPLETO (pra reconciliar os sem match) ==')
    for s in sorted(servicos, key=lambda x: norm(x.get('descricao'))):
        print(f'  {fmt(s)}')
