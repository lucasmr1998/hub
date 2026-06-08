"""READ-ONLY prod: acha metas ATIVAS com FK nula que quebram /crm/metas/."""
import sys
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
cur.execute("""SELECT tenant_id, id, tipo, vendedor_id, equipe_id, data_inicio, data_fim
               FROM crm_metas_vendas
               WHERE data_inicio <= CURRENT_DATE AND data_fim >= CURRENT_DATE
                 AND ((tipo='individual' AND vendedor_id IS NULL)
                      OR (tipo='equipe' AND equipe_id IS NULL))
               ORDER BY tenant_id;""")
rows = cur.fetchall()
print(f'Metas ATIVAS com FK nula (quebram a pagina): {len(rows)}')
for r in rows:
    print(f'  tenant={r[0]} id={r[1]} tipo={r[2]} vendedor_id={r[3]} equipe_id={r[4]} {r[5]}..{r[6]}')
c.close()
