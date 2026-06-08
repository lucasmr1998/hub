"""DIAGNOSTICO COMPLETO read-only: pagina ~500 msgs do uazapi (TR Carrion),
filtra mensagens de cliente, e cruza com Hubtrix prod (identificador_externo)
pra achar TODOS os gaps (recentes E antigos)."""
import sys, json
from datetime import datetime, timezone
from collections import defaultdict
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
token = (cfg or {}).get('token', '')
base = base.rstrip('/')
H = {'Accept':'application/json','Content-Type':'application/json','token':token}

# Pagina ate 500 msgs
todas = []
PAGE = 100
ALVO = 500
for p in range(ALVO // PAGE + 2):
    body = {'limit': PAGE, 'offset': len(todas)}
    r = requests.post(f'{base}/message/find', headers=H, json=body, timeout=20)
    if not r.ok:
        print(f'erro pagina {p}: {r.status_code} {r.text[:200]}'); break
    msgs = (r.json() or {}).get('messages', []) or []
    if not msgs:
        print(f'pagina {p}: 0 msgs, parando.'); break
    # detecta paginacao quebrada (mesma 1a msg que pagina anterior)
    if todas and msgs[0].get('messageid') == todas[-PAGE].get('messageid') if len(todas) >= PAGE else False:
        print(f'pagina {p}: paginacao parece nao avancar, parando.'); break
    todas.extend(msgs)
    ts_min = datetime.fromtimestamp(min(m.get('messageTimestamp',0) for m in msgs)/1000, tz=timezone.utc)
    ts_max = datetime.fromtimestamp(max(m.get('messageTimestamp',0) for m in msgs)/1000, tz=timezone.utc)
    print(f'pagina {p}: +{len(msgs)} (total={len(todas)}) | ts {ts_min} -> {ts_max}')
    if len(todas) >= ALVO:
        break

# Filtra: cliente, nao-grupo, nao-vazio
do_cliente = [m for m in todas
              if not m.get('fromMe')
              and '@g.us' not in (m.get('chatid') or '')
              and not m.get('isGroup')]
print(f'\ntotal puxado: {len(todas)}  |  mensagens de cliente: {len(do_cliente)}')

# Cruza com prod
ids = list({(m.get('messageid') or m.get('id')) for m in do_cliente if (m.get('messageid') or m.get('id'))})
print(f'ids unicos: {len(ids)}')
em_prod = set()
if ids:
    cur.execute("""SELECT identificador_externo FROM inbox_mensagens
WHERE tenant_id = 11 AND identificador_externo = ANY(%s);""", (ids,))
    em_prod = {r[0] for r in cur.fetchall()}
faltantes = [m for m in do_cliente if (m.get('messageid') or m.get('id')) not in em_prod]
print(f'em prod: {len(em_prod)}  |  FALTANTES: {len(faltantes)}\n')

# Agrupa por telefone (usa chatid sem @suffix)
por_chat = defaultdict(list)
for m in faltantes:
    chatid = m.get('chatid') or ''
    por_chat[chatid].append(m)

print(f'chats distintos faltando: {len(por_chat)}\n')
for chatid, lst in sorted(por_chat.items(), key=lambda x: -len(x[1])):
    lst.sort(key=lambda x: x.get('messageTimestamp',0))
    ts_min = datetime.fromtimestamp(lst[0].get('messageTimestamp',0)/1000, tz=timezone.utc)
    ts_max = datetime.fromtimestamp(lst[-1].get('messageTimestamp',0)/1000, tz=timezone.utc)
    sender = lst[0].get('senderName') or '(?)'
    print(f'== {chatid}  sender={sender!r}  {len(lst)} msg(s)  {ts_min} -> {ts_max}')
    for m in lst:
        ts = datetime.fromtimestamp(m.get('messageTimestamp',0)/1000, tz=timezone.utc)
        t = m.get('messageType')
        txt = (m.get('text') or '')[:60]
        print(f'   {ts}  {t:18s} {txt!r}')
c.close()
