"""Pega status completo + descobre como filtrar /message/find por janela de tempo."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2, requests
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
cur.execute("SELECT base_url, configuracoes_extras FROM integracoes_api WHERE id=19;")
base, cfg = cur.fetchone()
token = (cfg or {}).get('token','')
c.close()
base = base.rstrip('/')
H = {'Accept':'application/json','Content-Type':'application/json','token':token}

# 1. STATUS COMPLETO
print('=== /instance/status (full) ===')
r = requests.get(f'{base}/instance/status', headers=H, timeout=15)
inst = r.json().get('instance', {})
for k in ('status','lastDisconnect','lastDisconnectReason','lastConnect','created','updated','owner','profileName'):
    print(f'  {k}: {inst.get(k)}')

# 2. /message/find — testar filtros
print('\n=== /message/find varios formatos ===')
# tentativa 1: limit + offset (sem filtro de data)
r = requests.post(f'{base}/message/find', headers=H, json={'limit':3}, timeout=15)
print('limit=3:', r.status_code)
data = r.json() if r.ok else {}
msgs = data.get('messages', [])[:1]
if msgs:
    print('  campos de uma mensagem:', sorted(msgs[0].keys()))
    print('  exemplo (1):', json.dumps({k: msgs[0].get(k) for k in ('messageid','chatid','sender','senderName','fromMe','messageTimestamp','messageType','content')}, ensure_ascii=False)[:400])

# tentativa 2: dateStart / dateEnd unix ms
janela_ini = 1748561546000  # 2026-05-29 21:32 UTC (~lastDisconnect)
janela_fim = 1748566440000  # 2026-05-30 00:54 UTC
for body in [
    {'limit': 3, 'startTimestamp': janela_ini, 'endTimestamp': janela_fim},
    {'limit': 3, 'fromTimestamp': janela_ini, 'toTimestamp': janela_fim},
    {'limit': 3, 'dateStart': janela_ini, 'dateEnd': janela_fim},
    {'limit': 3, 'startDate': janela_ini, 'endDate': janela_fim},
    {'limit': 3, 'fromMe': False, 'after': janela_ini},
]:
    r = requests.post(f'{base}/message/find', headers=H, json=body, timeout=15)
    n = len((r.json() or {}).get('messages', [])) if r.ok else -1
    print(f'  body={list(body.keys())} -> status={r.status_code} msgs_retornadas={n}')
