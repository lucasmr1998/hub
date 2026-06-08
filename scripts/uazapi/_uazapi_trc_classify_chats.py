"""Classifica os 7 chats com mensagens faltantes: grupo vs individual.
Usa /chat/find com filtro por id (testando varios formatos)."""
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
base = base.rstrip('/')
H = {'Accept':'application/json','Content-Type':'application/json','token':token}

CHATIDS = [
    '173349745463447@lid',
    '58364897796141@lid',
    '45484391587891@lid',
    '235630646820908@lid',
    '136851146944764@lid',
    '15612290007063@lid',
    '29691696136344@lid',
]

# Pega chats via /chat/find sem filtro (limit alto) e procura os interessantes
r = requests.post(f'{base}/chat/find', headers=H, json={'limit': 500}, timeout=20)
chats = (r.json() or {}).get('chats', []) or []
print(f'chats retornados: {len(chats)}')
if chats:
    print(f'campos de um chat: {sorted(chats[0].keys())[:40]}\n')

idx = {(c.get('id') or c.get('wa_chatid') or ''): c for c in chats}
for cid in CHATIDS:
    ch = idx.get(cid)
    if not ch:
        # tenta achar por algum campo
        match = [c for c in chats if cid in str(c)]
        if match:
            ch = match[0]
    if not ch:
        print(f'-- {cid}: NAO ENCONTRADO em /chat/find')
        continue
    relevantes = ['id','wa_chatid','wa_isGroup','wa_contactName','wa_groupSubject','name','phone','isGroup','groupSubject','contact','wa_name']
    snap = {k: ch.get(k) for k in relevantes if k in ch}
    print(f'-- {cid}')
    print(f'   {snap}')
c.close()
