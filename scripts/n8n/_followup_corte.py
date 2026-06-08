"""Injeta o corte 'atualizado_em > <ativacao>' nas queries Buscar Stale e Buscar
Esgotados do fluxo de follow-up (tYckyds4TqPpFOWd), pra so pegar conversas que
ficaram stale DEPOIS de ligar (nunca o backlog). Idempotente (re-stampa).
Sem --ativar: so injeta, fluxo segue inativo. Com --ativar: re-stampa + ativa.
NOW() vem do banco de prod (read-only) pra timezone bater.
"""
import sys, re, json, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
from pathlib import Path
from _n8n_api import N8N

ATIVAR = '--ativar' in sys.argv
WID = 'tYckyds4TqPpFOWd'
MARK = '-- corte_ativacao'

# 1. NOW() do banco de prod (read-only)
env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
cur = c.cursor(); cur.execute("SELECT NOW();")
cutoff = cur.fetchone()[0]; c.close()
cutoff_s = str(cutoff)  # 'YYYY-MM-DD HH:MM:SS.ffffff+00:00' — aceito pelo Postgres
print('corte (prod NOW()):', cutoff_s)

cut_line = f"  AND atualizado_em > '{cutoff_s}'  {MARK}"
re_existing = re.compile(r"\n\s*AND atualizado_em > '[^']*'\s*" + re.escape(MARK))
re_7d = re.compile(r"(\n\s*AND atualizado_em > NOW\(\) - INTERVAL '7 days')")

def aplicar(q):
    if re_existing.search(q):           # re-stampa
        return re_existing.sub('\n' + cut_line, q)
    return re_7d.sub(r"\1\n" + cut_line, q)  # insere apos a linha dos 7 dias

n = N8N(); w = n.get_workflow(WID); nodes = w['nodes']
for nd in nodes:
    if nd['name'] in ('Buscar Stale', 'Buscar Esgotados'):
        q0 = nd['parameters']['query']
        nd['parameters']['query'] = aplicar(q0)
        novo = [ln for ln in nd['parameters']['query'].splitlines() if MARK in ln]
        print(f"[{nd['name']}] linha de corte:", novo[0].strip() if novo else 'NAO INSERIDA!')

so = w.get('settings', {}) or {}
sl = {k: so[k] for k in ('executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in so}
n.update_workflow(WID, {'name': w['name'], 'nodes': nodes, 'connections': w['connections'], 'settings': sl})
print('PUT ok.')

if ATIVAR:
    n.activate_workflow(WID)
    print('FLUXO ATIVADO.')
else:
    w2 = n.get_workflow(WID)
    print('active:', w2.get('active'), '(inativo — corte baked, ativar com --ativar)')
