"""Read-only: dump COMPLETO de TokenHubsoft3 e Consulta dados cliente
(template pra os novos nos HTTP + alvos do repoint isAClient)."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
nodes = {nd['name']: nd for nd in w['nodes']}
for name in ('TokenHubsoft3', 'Consulta dados cliente'):
    nd = nodes.get(name)
    print(f'\n######## {name} ########')
    print(json.dumps(nd, ensure_ascii=False, indent=1))
