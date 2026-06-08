"""
Cliente Python pra API REST do N8N (TR Carrion).
Usa .env.n8n pra credenciais. Funcoes basicas: list, get, create, update, activate.

Uso direto via Python:
    from _n8n_api import N8N
    n8n = N8N()
    n8n.list_workflows()
    n8n.get_workflow('PeEAQN6y5ihbzXWF')
    n8n.create_workflow({...})
"""
import os
import json
import sys
from pathlib import Path
import requests

BASE = Path(__file__).parent.parent
ENV_FILE = BASE / '.env.n8n'


def _load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class N8N:
    def __init__(self):
        env = _load_env()
        self.base = env['N8N_BASE_URL'].rstrip('/')
        self.api_key = env['N8N_API_KEY']
        self.headers = {
            'X-N8N-API-KEY': self.api_key,
            'Accept': 'application/json',
        }

    def _req(self, method, path, **kwargs):
        url = f'{self.base}/api/v1{path}'
        headers = {**self.headers, **kwargs.pop('headers', {})}
        if 'json' in kwargs:
            headers['Content-Type'] = 'application/json'
        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if not resp.ok:
            raise RuntimeError(f'{method} {url} -> {resp.status_code}: {resp.text[:500]}')
        return resp.json() if resp.text else {}

    def list_workflows(self, active=None, limit=250):
        params = {'limit': limit}
        if active is not None:
            params['active'] = 'true' if active else 'false'
        return self._req('GET', '/workflows', params=params)

    def get_workflow(self, workflow_id):
        return self._req('GET', f'/workflows/{workflow_id}')

    def create_workflow(self, payload):
        return self._req('POST', '/workflows', json=payload)

    def update_workflow(self, workflow_id, payload):
        return self._req('PUT', f'/workflows/{workflow_id}', json=payload)

    def activate_workflow(self, workflow_id):
        return self._req('POST', f'/workflows/{workflow_id}/activate')

    def deactivate_workflow(self, workflow_id):
        return self._req('POST', f'/workflows/{workflow_id}/deactivate')

    def delete_workflow(self, workflow_id):
        return self._req('DELETE', f'/workflows/{workflow_id}')


# ============================================================================
# CLI auxiliar
# ============================================================================
if __name__ == '__main__':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    n8n = N8N()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if cmd == 'list':
        data = n8n.list_workflows()
        workflows = data.get('data', [])
        print(f'Total: {len(workflows)} workflows')
        for w in sorted(workflows, key=lambda x: x.get('name', '')):
            active = '🟢' if w.get('active') else '⚫'
            print(f"  {active} {w['id']:25s}  {w.get('name', '?')}")

    elif cmd == 'get':
        wf_id = sys.argv[2]
        data = n8n.get_workflow(wf_id)
        # so resumo
        print(f"ID:     {data.get('id')}")
        print(f"Name:   {data.get('name')}")
        print(f"Active: {data.get('active')}")
        print(f"Nodes:  {len(data.get('nodes', []))}")
        print(f"Tags:   {[t.get('name') for t in data.get('tags', [])]}")
        if '--full' in sys.argv:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    elif cmd == 'save':
        # baixa JSON completo pra arquivo local
        wf_id = sys.argv[2]
        out = BASE / 'scripts' / f'_n8n_workflow_{wf_id}.json'
        data = n8n.get_workflow(wf_id)
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'Salvo em: {out}')

    else:
        print(f'Comando desconhecido: {cmd}')
        print('Disponiveis: list, get <id>, get <id> --full, save <id>')
