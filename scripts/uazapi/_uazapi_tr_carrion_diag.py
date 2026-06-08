"""DIAGNOSTICO uazapi TR Carrion: pega base_url+token do prod DB (read-only),
bate em /instance/status, e tenta descobrir endpoints de historico."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
import requests
from pathlib import Path

env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
cur = c.cursor()

cur.execute("""SELECT id, nome, tenant_id, base_url, configuracoes_extras, ativa
FROM integracoes_api WHERE tipo='uazapi'
ORDER BY tenant_id, id;""")
print('=== uazapi integracoes em prod ===')
rows = cur.fetchall()
for r in rows:
    iid, nome, tid, base, cfg, ativa = r
    tk = (cfg or {}).get('token','') if isinstance(cfg, dict) else ''
    cur.execute("SELECT slug FROM sistema_tenant WHERE id=%s;", (tid,))
    slug = cur.fetchone()[0]
    print(f'  id={iid} tenant_id={tid} slug={slug} nome={nome!r} ativa={ativa}')
    print(f'    base_url={base}  token_len={len(tk)}')
c.close()

print('\n=== buscando o da TR Carrion (tenant_id=11) ===')
trc = next((r for r in rows if r[2] == 11), None)
if not trc:
    print('NAO ACHEI integracao uazapi TR Carrion'); sys.exit(0)
iid, nome, tid, base, cfg, ativa = trc
token = (cfg or {}).get('token','')
base = (base or '').rstrip('/')
H = {'Accept':'application/json','token':token}

print(f'usando base={base}  (token oculto, len={len(token)})\n')

# 1. /instance/status
print('--- GET /instance/status ---')
try:
    r = requests.get(f'{base}/instance/status', headers=H, timeout=15)
    print(f'  status={r.status_code}')
    print('  body:', json.dumps(r.json(), ensure_ascii=False)[:600] if r.headers.get('content-type','').startswith('application/json') else r.text[:300])
except Exception as e:
    print(f'  ERRO {e}')

# 2. tentativas de endpoints de historico
print('\n--- explorando endpoints de historico ---')
TESTS = [
    ('GET', '/chat/list', {}),
    ('GET', '/chat/getChats', {}),
    ('POST', '/chat/find', {}),
    ('POST', '/message/find', {'limit': 5}),
    ('POST', '/chat/messages', {'limit': 5}),
    ('GET', '/chat', {}),
    ('GET', '/instance/info', {}),
]
for method, path, payload in TESTS:
    try:
        if method == 'GET':
            r = requests.get(f'{base}{path}', headers={**H,'Content-Type':'application/json'}, timeout=10)
        else:
            r = requests.post(f'{base}{path}', headers={**H,'Content-Type':'application/json'}, json=payload, timeout=10)
        snippet = r.text[:140] if r.text else '(vazio)'
        print(f'  {method} {path:25s} -> {r.status_code} {snippet}')
    except Exception as e:
        print(f'  {method} {path:25s} -> EXC {e}')
