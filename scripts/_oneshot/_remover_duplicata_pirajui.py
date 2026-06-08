"""Remove a duplicata 'Pirajui' (sem acento, id=9) mantendo 'Pirajuí' (id=274)."""
import sys
import psycopg2
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

env_path = Path(__file__).resolve().parents[1] / '.env.prod_readonly'
env = {}
for line in env_path.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip()

conn = psycopg2.connect(
    host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
conn.autocommit = False
cur = conn.cursor()

try:
    cur.execute("SELECT id, cidade, estado FROM viabilidade_cidadeviabilidade WHERE id IN (9, 274);")
    print('Antes:')
    for r in cur.fetchall():
        print(f'  id={r[0]} cidade={r[1]!r} estado={r[2]!r}')

    cur.execute("DELETE FROM viabilidade_cidadeviabilidade WHERE id = 9 AND tenant_id = 11;")
    print(f'\nDELETE id=9: rows={cur.rowcount}')

    cur.execute("SELECT id, cidade, estado FROM viabilidade_cidadeviabilidade WHERE id IN (9, 274);")
    print('Depois:')
    for r in cur.fetchall():
        print(f'  id={r[0]} cidade={r[1]!r} estado={r[2]!r}')

    cur.execute("SELECT COUNT(*) FROM viabilidade_cidadeviabilidade WHERE tenant_id = 11;")
    print(f'\nTotal final no tenant: {cur.fetchone()[0]}')

    conn.commit()
    print('COMMIT.')
finally:
    cur.close()
    conn.close()
