"""READ-ONLY: acha qual tabela o follow-up esta lendo (vero_session ou outro nome)."""
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

print('=== tabelas com nome contendo session/vero ===')
cur.execute("""SELECT table_schema, table_name FROM information_schema.tables
WHERE table_name ILIKE '%session%' OR table_name ILIKE '%vero%'
ORDER BY table_schema, table_name;""")
for s, n in cur.fetchall():
    print(f'  {s}.{n}')

print('\n=== schemas existentes (top) ===')
cur.execute("SELECT DISTINCT table_schema FROM information_schema.tables ORDER BY 1;")
for (s,) in cur.fetchall():
    print(' ', s)
c.close()
