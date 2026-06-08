"""READ-ONLY prod: lista as Opcoes de Vencimento (crm_opcoes_vencimento)
do tenant Nuvyon. Filtra por tenant. Nao escreve nada.
"""
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

cur.execute("SELECT id, nome, slug FROM sistema_tenant WHERE slug ILIKE %s OR nome ILIKE %s;",
            ('%nuvyon%', '%nuvyon%'))
tenants = cur.fetchall()
print('Tenants Nuvyon:', tenants)
if not tenants:
    print('Nenhum tenant nuvyon.'); sys.exit(1)
tid = tenants[0][0]

cur.execute("""SELECT id, dia, descricao, id_externo, ativo, ordem
               FROM crm_opcoes_vencimento WHERE tenant_id=%s ORDER BY ordem, dia;""", (tid,))
rows = cur.fetchall()
print(f'\nOpcoes de vencimento do tenant {tid} ({len(rows)}):')
print('  id | dia | id_externo(HubSoft) | ativo | ordem | descricao')
for r in rows:
    print(f'  {r[0]} | dia {r[1]:>2} | ext={r[3]!r} | ativo={r[4]} | ord={r[5]} | {r[2]!r}')

c.close()
