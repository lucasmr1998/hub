"""Monitora execucoes do fluxo de follow-up por ate 15 min, reportando novas.
Para quando achar uma execucao com status=error OU quando completar a janela."""
import sys, time
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'tYckyds4TqPpFOWd'
n = N8N()

# pega o id da execucao mais recente AGORA pra so reportar as proximas
ex = n._req('GET', '/executions', params={'workflowId': WID, 'limit': 1})
items = ex.get('data', [])
last_seen = items[0]['id'] if items else None
print(f'monitor iniciado. ultima execucao conhecida: {last_seen}\n')

t_start = time.time()
DEADLINE = 15 * 60  # 15 min
vistos = set()
while time.time() - t_start < DEADLINE:
    try:
        ex = n._req('GET', '/executions', params={'workflowId': WID, 'limit': 10})
        for e in ex.get('data', []):
            eid = e['id']
            if eid == last_seen or eid in vistos:
                continue
            vistos.add(eid)
            status = e.get('status') or ('finished' if e.get('finished') else '?')
            mode = e.get('mode')
            started = e.get('startedAt')
            print(f'[+] exec {eid} mode={mode} started={started} status={status}')
            if status in ('error', 'crashed'):
                # detalha o erro
                try:
                    det = n._req('GET', f'/executions/{eid}', params={'includeData': 'true'})
                    err = det.get('data', {}).get('resultData', {}).get('error', {})
                    print(f'    ERRO: {err}')
                except Exception as ee:
                    print(f'    (nao consegui detalhar: {ee})')
                print('PARANDO no primeiro erro.')
                sys.exit(0)
    except Exception as e:
        print(f'erro na consulta: {e}')
    time.sleep(30)

print(f'\nmonitor encerrou (15min). novas execucoes vistas: {len(vistos)}')
