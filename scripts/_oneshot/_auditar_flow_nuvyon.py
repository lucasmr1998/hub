"""Read-only: audita o flow_103_v6 procurando residuos Megalink / pontos de atencao
pra operacao Nuvyon. Nao altera nada.
- URLs/hosts externos (destinos de integracao)
- mencoes 'megalink'/'mega' e termos de regiao/atendente conhecidos
- variaveis de config relevantes (webhook, empresa, ids, token)
- textos de plano legados (620/660/1GB/Deezer/Globo)
"""
import sys, json, re
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from collections import Counter

SRC = Path('robo/docs/context/clientes/nuvyon/implementacoes/flow_103_hubtrix_v6.json')
doc = json.loads(SRC.read_text(encoding='utf-8'))
flow = doc['flow']

# 1. hosts/urls
hosts = Counter()
url_nodes = []
for o in flow:
    d = o.get('data')
    if isinstance(d, dict):
        raw = json.dumps(d, ensure_ascii=False)
        for u in re.findall(r'https?://[^\s"\\}]+', raw):
            host = re.sub(r'^https?://', '', u).split('/')[0]
            hosts[host] += 1
            if d.get('url'):
                pass
        u = d.get('url')
        if isinstance(u, str) and u:
            url_nodes.append((o.get('id'), d.get('identifier', ''), u[:90]))

print('== HOSTS chamados no fluxo ==')
for h, c in hosts.most_common():
    print(f'  {c:3} x  {h}')

print('\n== Nodes com data.url (endpoints diretos) ==')
seen = set()
for nid, ident, u in url_nodes:
    key = u
    if key in seen: continue
    seen.add(key)
    print(f'  [{nid}] {ident}: {u}')

# 2. termos sensiveis
print('\n== Mencoes sensiveis (megalink / atendentes / regiao) ==')
termos = ['megalink', 'MEGALINK', 'Flaysi', 'Franklin', 'Deezer', 'Globo',
          '620MB', '660MB', '1GB Turbo', 'piaui', 'Piauí', 'Bom Jesus', 'Gilbués', 'Timon']
hits = Counter()
for o in flow:
    raw = json.dumps(o.get('data', {}), ensure_ascii=False)
    for t in termos:
        n = raw.count(t)
        if n:
            hits[t] += n
for t, n in hits.most_common():
    print(f'  {n:3} x  {t!r}')

# 3. variaveis de config
print('\n== Variaveis de config relevantes ==')
varsblk = None
for k, v in doc.items():
    if isinstance(v, dict) and any(isinstance(x, dict) and 'name' in x for x in v.values()):
        varsblk = v; break
alvo = ('webhook', 'url_api', 'empresa', 'token', 'id_vendedor', 'id_origem',
        'servidor', 'nome_empresa', 'matrix')
if varsblk:
    for vid, info in varsblk.items():
        nome = info.get('name', '')
        val = str(info.get('value', ''))
        if any(a in nome.lower() for a in alvo) and val:
            show = val if len(val) < 70 else val[:67] + '...'
            print(f'  {nome} = {show!r}')
else:
    print('  (bloco de variaveis nao localizado)')
