"""Monitor v3: corre ate 60min, filtra por startedAt >= ativacao, para na primeira
execucao com atividade real (Stale/Esgotados > 0) ou no primeiro erro."""
import sys, time
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'tYckyds4TqPpFOWd'
ATIVACAO = '2026-05-29T21:53:59Z'
INTERESSE = ['Buscar Stale', 'Buscar Esgotados', 'Enviar Followup',
             'Transferir Fila', 'Marcar Enviado', 'Marcar Aguarda Humano']

n = N8N()

def itens_no(runs):
    try: return len((runs[0].get('data') or {}).get('main', [[]])[0])
    except: return 0

print(f'monitor v3 — filtrando por startedAt >= {ATIVACAO}\n')
vistos = set()
DEADLINE = 60 * 60
t_start = time.time()
while time.time() - t_start < DEADLINE:
    try:
        lst = n._req('GET', '/executions', params={'workflowId': WID, 'limit': 20}).get('data', [])
        novos = [e for e in lst if (e.get('startedAt') or '') >= ATIVACAO and e['id'] not in vistos]
        for e in sorted(novos, key=lambda x: x.get('startedAt', '')):
            eid = e['id']; vistos.add(eid)
            status = e.get('status') or ('finished' if e.get('finished') else '?')
            try:
                det = n._req('GET', f'/executions/{eid}', params={'includeData': 'true'})
                run = ((det.get('data') or {}).get('resultData') or {}).get('runData') or {}
                cont = {nm: itens_no(run.get(nm) or []) for nm in INTERESSE}
            except Exception as ie:
                cont = {}
                print(f'  (sem detalhe {eid}: {ie})')
            interessantes = ' '.join(f'{k}={v}' for k, v in cont.items() if v > 0)
            print(f'[{e.get("startedAt")}] exec {eid} status={status} {interessantes or "(vazio)"}')

            if status in ('error', 'crashed'):
                print('  ERRO. parando.'); sys.exit(0)
            if cont.get('Buscar Stale', 0) > 0 or cont.get('Buscar Esgotados', 0) > 0:
                print('  >>> PRIMEIRA ATIVIDADE REAL — parando.'); sys.exit(0)
    except Exception as e:
        print(f'erro: {e}')
    time.sleep(45)

print(f'\nmonitor encerrou (60min). execucoes pos-ativacao vistas: {len(vistos)}')
