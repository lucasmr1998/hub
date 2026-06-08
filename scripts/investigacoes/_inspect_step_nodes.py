"""Mostra detalhes dos Step nodes do workflow Vero."""
import json
import sys
import io
import requests
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']

r = requests.get(f'{BASE}/api/v1/workflows/Df1BgcXdg3HAUZwf', headers={'X-N8N-API-KEY': KEY}, timeout=15)
wf = r.json()
for n in wf['nodes']:
    name = n.get('name', '')
    if name.startswith('Step ') or name in ('Enviar Wazapi', 'Enviar Lead Hubtrix'):
        print(f'\n=== {name} ({n["type"].split(".")[-1]}) ===')
        print(json.dumps(n.get('parameters', {}), indent=2, ensure_ascii=False)[:2000])
