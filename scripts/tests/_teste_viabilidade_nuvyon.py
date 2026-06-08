"""Teste de viabilidade HubSoft (artelecom/Nuvyon).
1. Pega 1 endereco real de lead do tenant 12 (prod, READ-ONLY) — nao ecoa PII (so cidade/UF).
2. Autentica na HubSoft artelecom (.env.nuvyon_hubsoft).
3. POST /api/v1/integracao/mapeamento/viabilidade/consultar (tipo_busca=endereco).
4. Resume o resultado (viavel? projetos/caixas/portas). Sem secrets.
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
import psycopg2, requests

# --- 1. endereco de um lead real (tenant 12) ---
penv = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); penv[k.strip()] = v.strip()
c = psycopg2.connect(host=penv['PROD_DB_HOST'], port=penv['PROD_DB_PORT'],
    dbname=penv['PROD_DB_NAME'], user=penv['PROD_DB_USER'],
    password=penv['PROD_DB_PASSWORD'], connect_timeout=10)
cur = c.cursor()
cur.execute("""SELECT rua, numero_residencia, bairro, cidade, estado, cep
               FROM leads_prospectos
               WHERE tenant_id=12 AND COALESCE(rua,'')<>'' AND COALESCE(cidade,'')<>''
               ORDER BY data_cadastro DESC LIMIT 1;""")
row = cur.fetchone()
c.close()
if not row:
    print('Nenhum lead do tenant 12 com endereco preenchido. Me passe um endereco/CEP de teste.')
    sys.exit(0)
rua, numero, bairro, cidade, estado, cep = row
print(f'Endereco de teste (lead real tenant 12): cidade={cidade!r} UF={estado!r} CEP={cep!r} (rua/numero ocultos)')

# --- 2. token artelecom ---
henv = {}
for l in (Path('.env.nuvyon_hubsoft')).read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); henv[k.strip()] = v.strip()
BASE = henv['HUBSOFT_HOST'].rstrip('/')
tok = requests.post(f'{BASE}/oauth/token', json={
    'client_id': henv['HUBSOFT_CLIENT_ID'], 'client_secret': henv['HUBSOFT_CLIENT_SECRET'],
    'username': henv['HUBSOFT_USERNAME'], 'password': henv['HUBSOFT_PASSWORD'],
    'grant_type': henv['HUBSOFT_GRANT_TYPE'],
}, timeout=30)
tok.raise_for_status()
access = tok.json().get('access_token', '')
print('Token artelecom:', 'OK' if access else 'FALHOU')

# --- 3. consulta viabilidade ---
payload = {
    'tipo_busca': 'endereco',
    'raio': 250,
    'endereco': {
        'numero': str(numero or 'S/N'),
        'endereco': rua,
        'bairro': bairro or '',
        'cidade': cidade,
        'estado': (estado or '').upper(),
    },
    'detalhar_portas': True,
}
r = requests.post(f'{BASE}/api/v1/integracao/mapeamento/viabilidade/consultar',
                  headers={'Authorization': f'Bearer {access}', 'Content-Type': 'application/json'},
                  json=payload, timeout=45)
print(f'\nHTTP {r.status_code}')
try:
    data = r.json()
except Exception:
    print('resp bruta:', r.text[:300]); sys.exit(0)

print('status:', data.get('status'))
res = data.get('resultado') or {}
print('\nResultado (estrutura, truncado):')
print(json.dumps(res, ensure_ascii=False, indent=1)[:2200])
print('\nmsg:', str(data.get('msg') or data.get('message') or '')[:200])
