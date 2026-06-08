"""Monitor v2 do fluxo de follow-up: corre ate 60min, para na PRIMEIRA execucao
com atividade real (Buscar Stale ou Esgotados com >0 itens) ou no primeiro erro.
Reporta cada execucao com a contagem de itens dos nodes-chave."""
import sys, time
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'tYckyds4TqPpFOWd'
INTERESSANTES = ['Buscar Stale', 'Buscar Esgotados', 'Enviar Followup',
                 'Transferir Fila', 'Marcar Enviado', 'Marcar Aguarda Humano']

n = N8N()

def itens_no(runs):
    try:
        return len((runs[0].get('data') or {}).get('main', [[]])[0])
    except Exception:
        return -1

ex = n._req('GET', '/executions', params={'workflowId': WID, 'limit': 1})
items = ex.get('data', [])
last = items[0]['id'] if items else None
print(f'monitor v2. ultima conhecida={last}\n')

DEADLINE = 60 * 60
t_start = time.time()
vistos = set()
while time.time() - t_start < DEADLINE:
    try:
        lst = n._req('GET', '/executions', params={'workflowId': WID, 'limit': 10}).get('data', [])
        for e in lst:
            eid = e['id']
            if eid == last or eid in vistos:
                continue
            vistos.add(eid)
            status = e.get('status') or ('finished' if e.get('finished') else '?')
            try:
                det = n._req('GET', f'/executions/{eid}', params={'includeData': 'true'})
                run = ((det.get('data') or {}).get('resultData') or {}).get('runData') or {}
                contagens = {nome: itens_no(run.get(nome) or []) for nome in INTERESSANTES}
            except Exception as ie:
                contagens = {}
                print(f'  (nao consegui detalhar {eid}: {ie})')
            resumo = ' '.join(f'{k}={v}' for k, v in contagens.items() if v != 0)
            print(f'[{e.get("startedAt")}] exec {eid} status={status} {resumo or "(vazio)"}')

            if status in ('error', 'crashed'):
                print('  ERRO detectado, parando.')
                sys.exit(0)
            if (contagens.get('Buscar Stale', 0) > 0 or
                contagens.get('Buscar Esgotados', 0) > 0):
                print('  >>> PRIMEIRA ATIVIDADE REAL — parando monitor.')
                sys.exit(0)
    except Exception as e:
        print(f'erro: {e}')
    time.sleep(30)

print(f'\nmonitor encerrou (60min sem atividade). execucoes vistas: {len(vistos)}')
