"""Tenta ativar a copia Nuvyon kIGvBSkGBUDpO2V4 e reporta o resultado/erro real.
Lista os webhooks (paths) pra diagnostico de colisao.
"""
import sys
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
print(f'Alvo: {w["name"]}  active={w.get("active")}')

print('\nWebhooks no fluxo:')
for nd in w['nodes']:
    if nd.get('type', '').endswith('webhook'):
        p = nd.get('parameters', {})
        print(f"  {nd['name']:24s} path={p.get('path')!r} method={p.get('httpMethod','GET')}")

print('\nTentando ativar...')
try:
    r = n.activate_workflow(WID)
    print('OK ->', r.get('active') if isinstance(r, dict) else r)
except Exception as e:
    print('FALHOU:')
    print(' ', str(e)[:800])

w2 = n.get_workflow(WID)
print('\nactive agora:', w2.get('active'))
