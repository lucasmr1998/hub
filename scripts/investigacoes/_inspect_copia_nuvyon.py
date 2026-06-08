"""Inspeciona a copia fresca kIGvBSkGBUDpO2V4 pra montar o De->Para do repoint Nuvyon.
Read-only. Nao ecoa secrets (so nomes/ids de credencial e URLs/hosts).
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
print(f'{w["name"]}  nodes={len(nodes)} active={w.get("active")}\n')

# 1. webhooks (path)
print('== WEBHOOKS ==')
for nd in nodes:
    if nd.get('type', '').endswith('webhook'):
        p = nd.get('parameters', {})
        print(f'  {nd["name"]:40s} path={p.get("path")!r} method={p.get("httpMethod","")}')

# 2. nodes HTTP por host
print('\n== HTTP (host na URL) ==')
import re
for nd in nodes:
    p = nd.get('parameters', {})
    url = p.get('url', '') or ''
    if isinstance(url, str) and ('http' in url or '{#' in url or '{{' in url):
        host = re.sub(r'^https?://', '', url).split('/')[0][:60]
        print(f'  {nd["name"]:40s} {host}')

# 3. empresa MEGALINK
print('\n== MEGALINK nos parametros ==')
mega = []
for nd in nodes:
    raw = json.dumps(nd.get('parameters', {}), ensure_ascii=False)
    if 'MEGALINK' in raw or 'megalink' in raw.lower():
        mega.append(nd['name'])
print('  nos:', mega)

# 4. hubsoft
print('\n== nos com hubsoft.com.br ==')
for nd in nodes:
    raw = json.dumps(nd.get('parameters', {}), ensure_ascii=False)
    if 'hubsoft.com.br' in raw:
        m = re.findall(r'[a-z0-9.]+hubsoft\.com\.br', raw)
        print(f'  {nd["name"]:40s} {set(m)}')

# 5. credenciais referenciadas
print('\n== CREDENCIAIS (tipo -> nome/id) ==')
seen = {}
for nd in nodes:
    for ctype, cval in (nd.get('credentials', {}) or {}).items():
        key = (ctype, cval.get('name'), cval.get('id'))
        seen.setdefault(key, []).append(nd['name'])
for (ctype, cname, cid), users in sorted(seen.items()):
    print(f'  {ctype:30s} {cname!r} (id={cid})  x{len(users)}')
