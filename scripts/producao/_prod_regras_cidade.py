"""READ-ONLY prod: mostra as regras de automacao do pipeline (tenant 11),
destacando as que mexem com cidade/agente (a regra da Flavia)."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
from pathlib import Path

env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
cur = c.cursor()
cur.execute("""SELECT id, nome, ativo, estagio_id, prioridade, condicoes, acoes, total_disparos
               FROM crm_regras_pipeline_estagio WHERE tenant_id=11 ORDER BY prioridade, id;""")
rows = cur.fetchall()
print(f'Regras de automacao do tenant 11: {len(rows)}\n')
for r in rows:
    rid, nome, ativo, est, prio, cond, acoes, disp = r
    blob = json.dumps(cond, ensure_ascii=False) + json.dumps(acoes, ensure_ascii=False)
    flag = '  <<< CIDADE/AGENTE' if any(k in blob.lower() for k in ('cidade','agente','flavia','palho')) else ''
    print(f'[{rid}] {nome!r} ativo={ativo} estagio={est} prio={prio} disparos={disp}{flag}')
    print('   condicoes:', json.dumps(cond, ensure_ascii=False))
    print('   acoes    :', json.dumps(acoes, ensure_ascii=False))
c.close()
