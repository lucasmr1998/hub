"""Read-only: conexoes cruas (com indice de saida) dos nos da decisao de cobertura."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
conns = w['connections']

for name in ('CheckErrorCEP1', 'SelecionarCidade1', 'If', 'Merge1', 'Edit Fields10', 'ViaCEP1', 'HasValidCPFToSearch?1', 'TokenHubsoft3'):
    c = conns.get(name)
    print(f'\n### {name}')
    if not c:
        print('  (sem saidas)'); continue
    for outtype, branches in c.items():
        for i, grp in enumerate(branches or []):
            tgts = [(cc['node'], cc.get('index', 0)) for cc in (grp or [])]
            print(f'  {outtype}[{i}] -> {tgts}')
