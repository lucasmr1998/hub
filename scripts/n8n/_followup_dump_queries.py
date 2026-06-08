import sys
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N
w = N8N().get_workflow('tYckyds4TqPpFOWd')
print('active:', w.get('active'))
for nd in w['nodes']:
    if nd['name'] in ('Buscar Stale', 'Buscar Esgotados'):
        print('\n===', nd['name'], '===')
        print(nd['parameters']['query'])
