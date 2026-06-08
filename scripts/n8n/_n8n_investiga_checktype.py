"""Read-only: investiga o CheckTypeWebhook na copia Nuvyon kIGvBSkGBUDpO2V4.
- o no esta disabled? tem conexoes downstream (eh usado)?
- algum no chama o path CheckType internamente (HTTP)?
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
PATH = '8a61fb9e-5558-4d3f-ace7-2295df84de6e-CheckType'
n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
conns = w['connections']

ct = next((nd for nd in nodes if nd.get('name') == 'CheckTypeWebhook'), None)
print('CheckTypeWebhook:')
print('  disabled:', ct.get('disabled', False))
print('  type    :', ct.get('type'))
print('  downstream conns:', conns.get('CheckTypeWebhook', {}))

# quem chama o path internamente
print('\nNos que referenciam o path CheckType:')
achou = False
for nd in nodes:
    raw = json.dumps(nd.get('parameters', {}), ensure_ascii=False)
    if PATH in raw or 'CheckType' in raw:
        achou = True
        url = nd.get('parameters', {}).get('url', '')
        print(f"  {nd['name']} ({nd['type'].split('.')[-1]}) url={url[:90]!r}")
if not achou:
    print('  nenhum (CheckTypeWebhook nao eh chamado dentro da copia)')

# resumo de todos os webhooks
print('\nTodos os webhooks da copia:')
for nd in nodes:
    if nd.get('type', '').endswith('webhook'):
        print(f"  {nd['name']:22s} path={nd.get('parameters',{}).get('path')!r} disabled={nd.get('disabled',False)}")
