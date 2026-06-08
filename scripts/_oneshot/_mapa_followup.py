"""Mapeia o fluxo de follow-up Vero no N8N: trigger/agenda, criterio de busca,
quantos disparos/tentativas e o que faz depois. Read-only."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'tYckyds4TqPpFOWd'  # [Vero] Follow-up Abandonados D+2h
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
print(f'{w["name"]}  active={w.get("active")}  nodes={len(nodes)}')

print('\n== Nodes (nome | tipo) ==')
for nd in nodes:
    t = nd.get('type', '').split('.')[-1]
    print(f'  {nd["name"]:34s} {t}')

# trigger / schedule
print('\n== Trigger/Schedule ==')
for nd in nodes:
    t = nd.get('type', '')
    if 'trigger' in t.lower() or 'cron' in t.lower() or 'schedule' in t.lower():
        print(f'  {nd["name"]} [{t.split(".")[-1]}]:', json.dumps(nd.get('parameters', {}), ensure_ascii=False)[:400])

# nos que mencionam tentativa/contador/follow/stale (criterio + cadencia)
print('\n== Nos com tentativa/contador/stale/follow/disparo ==')
for nd in nodes:
    raw = json.dumps(nd.get('parameters', {}), ensure_ascii=False)
    low = (nd['name'] + raw).lower()
    if any(k in low for k in ('tentativa', 'contador', 'stale', 'follow', 'disparo', 'count', 'numero_followup', 'qtd')):
        print(f'\n  -- {nd["name"]} [{nd["type"].split(".")[-1]}] --')
        print('   ', raw[:500])
