"""Read-only check: tr-carrion tem pipeline + estagios em prod?"""
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')
conn = psycopg2.connect(
    host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
    database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
cur = conn.cursor()

cur.execute("SELECT id, slug, nome, ativo FROM sistema_tenant WHERE slug = 'tr-carrion';")
t = cur.fetchone()
print('TENANT:', t)
if not t:
    raise SystemExit('tenant tr-carrion nao existe!')
tid = t[0]

cur.execute("SELECT id, nome, padrao, ativo FROM crm_pipelines WHERE tenant_id = %s;", (tid,))
pipelines = cur.fetchall()
print(f'\nPIPELINES ({len(pipelines)}):')
for p in pipelines:
    print(' ', p)

for p in pipelines:
    pid = p[0]
    cur.execute("SELECT id, nome, ordem, ativo, is_final_ganho, is_final_perdido FROM crm_estagios WHERE pipeline_id = %s ORDER BY ordem;", (pid,))
    estagios = cur.fetchall()
    print(f'\n  ESTAGIOS do pipeline {pid} ({len(estagios)}):')
    for e in estagios:
        print('   ', e)

cur.close()
conn.close()
