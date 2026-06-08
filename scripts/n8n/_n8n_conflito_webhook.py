"""Acha qual webhook da copia Nuvyon (kIGvBSkGBUDpO2V4) colide com outro workflow ATIVO.
Lista, entre os workflows ativos, quem usa os paths 'nuvyion1' e o CheckType.
"""
import sys
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
copia = n.get_workflow(WID)
meus = {}
for nd in copia['nodes']:
    if nd.get('type', '').endswith('webhook'):
        meus[nd['name']] = nd.get('parameters', {}).get('path')
print('Webhooks da copia:', meus)

alvo_paths = set(meus.values())
print('\nProcurando esses paths em outros workflows ATIVOS...')
data = n.list_workflows(active=True).get('data', [])
for w in data:
    if w['id'] == WID:
        continue
    full = n.get_workflow(w['id'])
    for nd in full['nodes']:
        if nd.get('type', '').endswith('webhook'):
            p = nd.get('parameters', {}).get('path')
            if p in alvo_paths:
                print(f"  CONFLITO: path {p!r} usado por '{w['name']}' ({w['id']}) no no '{nd['name']}'")
print('\n(fim)')
