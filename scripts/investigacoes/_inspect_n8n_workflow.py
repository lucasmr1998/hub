"""Mostra estrutura completa de um workflow N8N."""
import json
import sys
import requests
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']

wf_id = sys.argv[1] if len(sys.argv) > 1 else 'Df1BgcXdg3HAUZwf'

r = requests.get(f'{BASE}/api/v1/workflows/{wf_id}', headers={'X-N8N-API-KEY': KEY}, timeout=15)
wf = r.json()

print(f"Workflow: {wf['name']} (active={wf['active']})\n")

for n in wf['nodes']:
    name = n['name']
    ntype = n['type'].split('.')[-1]
    print(f"  [{ntype:25}] {name}")
    if ntype == 'webhook':
        params = n.get('parameters', {})
        print(f"      path:    {params.get('path')}")
        print(f"      method:  {params.get('httpMethod')}")
        print(f"      respond: {params.get('responseMode')}")

print('\nWebhook URL externa (se for trigger):')
for n in wf['nodes']:
    if 'webhook' in n['type'].lower():
        path = n.get('parameters', {}).get('path', '')
        print(f'  {BASE}/webhook/{path}')
        print(f'  {BASE}/webhook-test/{path}  (modo test no editor)')
