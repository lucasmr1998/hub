"""Read-only: dump dos nos chave da decisao de cobertura do validador Nuvyon."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
nodes = {nd['name']: nd for nd in w['nodes']}

for name in ('CheckErrorCEP1', 'SelecionarCidade1', 'If', 'Edit Fields21', 'Edit Fields8', 'Merge1', 'ViaCEP1'):
    nd = nodes.get(name)
    if not nd:
        print(f'\n### {name}: NAO ENCONTRADO'); continue
    print(f'\n### {name}  [{nd["type"].split(".")[-1]}]  id={nd.get("id")}')
    print(json.dumps(nd.get('parameters', {}), ensure_ascii=False, indent=1)[:1600])
