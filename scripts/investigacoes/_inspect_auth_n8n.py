"""Inspeciona padrao de auth N8N->Hubtrix (no orquestrador) e a credencial Postgres
do fluxo de follow-up. NAO ecoa valores de segredo (so estrutura)."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

n = N8N()

# 1. follow-up: credencial Postgres + base do schedule
fu = n.get_workflow('tYckyds4TqPpFOWd')
for nd in fu['nodes']:
    if nd.get('type','').endswith('postgres'):
        print('FOLLOWUP postgres node:', nd['name'], '| cred:', nd.get('credentials'))

# 2. orquestrador: nos http que chamam /public/n8n/ (auth header)
orq = n.get_workflow('Df1BgcXdg3HAUZwf')
print('\nORQUESTRADOR nodes http p/ hubtrix /public/n8n/:')
for nd in orq['nodes']:
    if not nd.get('type','').endswith('httpRequest'):
        continue
    url = nd.get('parameters',{}).get('url','') or ''
    if 'public/n8n' in url or 'hubtrix' in url.lower():
        p = nd.get('parameters', {})
        hp = p.get('headerParameters', {}).get('parameters', [])
        # mascara o valor do secret
        hdrs = [{'name': h.get('name'), 'tem_valor': bool(h.get('value'))} for h in hp]
        print(f"  {nd['name']:30s} method={p.get('method')} sendHeaders={p.get('sendHeaders')} authentication={p.get('authentication')}")
        print(f"     url: {url[:75]}")
        print(f"     headers: {hdrs}  | credentials: {list((nd.get('credentials') or {}).keys())}")
