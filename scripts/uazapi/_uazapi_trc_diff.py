"""DIAGNOSTICO read-only: descobre o gap entre a ultima mensagem recebida pela
inbox TR Carrion (em prod) e o que o uazapi tem armazenado mais novo. Reporta
quantas/quais estao faltando, sem inserir nada."""
import sys, json, time
from datetime import datetime, timezone
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2, requests
from pathlib import Path

# 1. credenciais prod
env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
cur = c.cursor()

# 2. ultima mensagem de contato (remetente_tipo='contato') na inbox TR Carrion
cur.execute("""SELECT data_envio, identificador_externo
FROM inbox_mensagens
WHERE tenant_id = 11 AND remetente_tipo = 'contato'
ORDER BY data_envio DESC LIMIT 1;""")
row = cur.fetchone()
if not row:
    print('Nenhuma mensagem de contato encontrada para tenant 11.'); sys.exit(0)
ult_data, ult_ext = row
print(f'ULTIMA recebida em prod: {ult_data}  externo={ult_ext}')
cutoff_ms = int(ult_data.replace(tzinfo=timezone.utc).timestamp() * 1000) if ult_data.tzinfo is None else int(ult_data.timestamp() * 1000)
print(f'cutoff_ms (UTC): {cutoff_ms}\n')

# 3. credencial uazapi (integracao id=19, tenant 11)
cur.execute("SELECT base_url, configuracoes_extras FROM integracoes_api WHERE id=19;")
base, cfg = cur.fetchone()
token = (cfg or {}).get('token', '')
base = base.rstrip('/')
H = {'Accept':'application/json','Content-Type':'application/json','token':token}

# 4. puxa mensagens do uazapi (mais recentes primeiro). Pagina ate cobrir o cutoff
todas = []
offset = 0
PAGE = 100
MAX_PAGES = 50
for p in range(MAX_PAGES):
    body = {'limit': PAGE, 'offset': offset}
    r = requests.post(f'{base}/message/find', headers=H, json=body, timeout=20)
    if not r.ok:
        print(f'erro pagina {p}: {r.status_code} {r.text[:200]}'); break
    data = r.json() or {}
    msgs = data.get('messages', []) or []
    if not msgs:
        break
    todas.extend(msgs)
    min_ts = min((m.get('messageTimestamp') or 0) for m in msgs)
    print(f'pagina {p}: +{len(msgs)} (total={len(todas)}) | min_ts={datetime.fromtimestamp(min_ts/1000, tz=timezone.utc)}')
    if min_ts <= cutoff_ms:
        break
    if not data.get('hasMore', False):
        break
    offset += PAGE

# 5. filtra: mais novas que o cutoff, fromMe=false, nao-grupo
novas = [m for m in todas
         if (m.get('messageTimestamp') or 0) > cutoff_ms
         and not m.get('fromMe')
         and '@g.us' not in (m.get('chatid') or '')
         and not (m.get('isGroup'))]

print(f'\nmensagens puxadas total: {len(todas)}')
print(f'mais novas que cutoff + de cliente + nao-grupo: {len(novas)}')

# 6. cruza com prod (identificador_externo)
ids = [(m.get('messageid') or m.get('id')) for m in novas if (m.get('messageid') or m.get('id'))]
ja_em_prod = set()
if ids:
    cur.execute("""SELECT identificador_externo FROM inbox_mensagens
WHERE tenant_id = 11 AND identificador_externo = ANY(%s);""", (ids,))
    ja_em_prod = {r[0] for r in cur.fetchall()}
faltantes = [m for m in novas if (m.get('messageid') or m.get('id')) not in ja_em_prod]
print(f'ja em prod: {len(ja_em_prod)}')
print(f'FALTANDO (gap): {len(faltantes)}')

# 7. amostra agrupada por telefone
from collections import defaultdict
por_tel = defaultdict(list)
for m in faltantes:
    chatid = m.get('chatid') or ''
    tel = chatid.split('@')[0] if chatid else ''
    por_tel[tel].append(m)
print(f'\ntelefones distintos no gap: {len(por_tel)}')
for tel, lst in sorted(por_tel.items(), key=lambda x: -len(x[1]))[:10]:
    ts_min = min(m.get('messageTimestamp') or 0 for m in lst)
    ts_max = max(m.get('messageTimestamp') or 0 for m in lst)
    sample = (lst[0].get('content') or {}).get('text','') or lst[0].get('text','')
    print(f'  {tel}: {len(lst)} msg(s)  janela={datetime.fromtimestamp(ts_min/1000, tz=timezone.utc)} -> {datetime.fromtimestamp(ts_max/1000, tz=timezone.utc)}')
    print(f'     ex: {(sample or "[sem texto]")[:80]!r}')
c.close()
