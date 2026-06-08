"""Backup + mapa do ramo de validacao de CEP da copia Nuvyon (kIGvBSkGBUDpO2V4).
READ-ONLY (so backup). Mostra:
- contagem/lista de nos (apos trim da UI)
- nos relacionados a CEP/cobertura (ViaCEP, BrasilAPI, givesServiceToCity, hubsoft, viabilidade)
- conexoes ao redor desses nos (pra saber onde inserir)
"""
import sys, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
conns = w['connections']
print(f'{w["name"]}  active={w.get("active")}  nodes={len(nodes)}')

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_nuvyon_PREVIAB_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)

KW = ('cep', 'viacep', 'brasilapi', 'givesservice', 'cobertura', 'viabil',
      'hubsoft', 'token', 'localidade', 'bairro')
print('\n== Nos relacionados a CEP/cobertura ==')
rel = []
for nd in nodes:
    blob = (nd.get('name','') + ' ' + json.dumps(nd.get('parameters',{}), ensure_ascii=False)).lower()
    if any(k in blob for k in KW):
        rel.append(nd['name'])
        url = nd.get('parameters',{}).get('url','')
        print(f"  {nd['name']:34s} [{nd['type'].split('.')[-1]}] {str(url)[:70]}")

print('\n== Conexoes (saidas) dos nos relacionados ==')
for name in rel:
    outs = conns.get(name, {}).get('main', [])
    targets = [c['node'] for grp in (outs or []) for c in (grp or [])]
    if targets:
        print(f"  {name} -> {targets}")

print('\n== Quem alimenta esses nos (entradas) ==')
for name in rel:
    feeders = []
    for src, c in conns.items():
        for grp in c.get('main', []) or []:
            for cc in (grp or []):
                if cc['node'] == name:
                    feeders.append(src)
    if feeders:
        print(f"  {name} <- {feeders}")
