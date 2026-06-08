"""Lista executions recentes do workflow Vero pra diagnosticar."""
import json
import requests
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
WF_ID = 'Df1BgcXdg3HAUZwf'

r = requests.get(f'{BASE}/api/v1/executions',
                 params={'workflowId': WF_ID, 'limit': 10},
                 headers={'X-N8N-API-KEY': KEY}, timeout=15)
data = r.json()
execs = data.get('data', data) if isinstance(data, dict) else data

print(f'Executions ({len(execs)}):\n')
for e in execs:
    eid = e.get('id')
    started = e.get('startedAt')
    stopped = e.get('stoppedAt')
    status = e.get('status') or ('success' if e.get('finished') else 'unknown')
    mode = e.get('mode')
    print(f'  id={eid} started={started}  status={status} mode={mode}')

# Pega a mais recente e mostra detalhes
if execs:
    latest = execs[0]
    print(f'\n=== Detalhe da execution {latest["id"]} ===')
    r = requests.get(f'{BASE}/api/v1/executions/{latest["id"]}',
                     params={'includeData': 'true'},
                     headers={'X-N8N-API-KEY': KEY}, timeout=20)
    detail = r.json()

    print(f'finished:    {detail.get("finished")}')
    print(f'status:      {detail.get("status")}')
    print(f'startedAt:   {detail.get("startedAt")}')
    print(f'stoppedAt:   {detail.get("stoppedAt")}')
    print(f'mode:        {detail.get("mode")}')

    err = detail.get('data', {}).get('resultData', {}).get('error')
    if err:
        print(f'\nERROR:')
        print(json.dumps(err, indent=2, ensure_ascii=False)[:2000])

    last_run_data = detail.get('data', {}).get('resultData', {}).get('runData', {})
    print(f'\nNodos executados ({len(last_run_data)}):')
    for node_name, runs in last_run_data.items():
        for run in runs:
            err = run.get('error')
            ms = run.get('executionTime', '?')
            n_items = sum(len(out) for out in (run.get('data', {}).get('main') or []) if out)
            if err:
                print(f'  [ERR] {node_name:30} ({ms}ms) error.message={err.get("message")}')
            else:
                print(f'  [OK ] {node_name:30} ({ms}ms) items={n_items}')
