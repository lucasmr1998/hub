"""Diagnostica o webhook QuestionValidator e forca re-registro (deactivate->activate)."""
import sys
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'kIGvBSkGBUDpO2V4'
n = N8N()
w = n.get_workflow(WID)
print('active:', w.get('active'))
for nd in w['nodes']:
    if nd.get('type','').endswith('webhook'):
        p = nd.get('parameters', {})
        print(f"  {nd['name']:22s} path={p.get('path')!r} method={p.get('httpMethod','GET')!r}")

print('\nciclo desativa->ativa...')
try:
    n.deactivate_workflow(WID)
except Exception as e:
    print('deactivate:', str(e)[:150])
r = n.activate_workflow(WID)
print('activate ->', r.get('active') if isinstance(r, dict) else r)
