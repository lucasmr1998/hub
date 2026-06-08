"""READ-ONLY prod: verifica se leads da Nuvyon (tenant 12) estao chegando no Hubtrix.
Introspecta colunas de leads_prospectos, conta, e mostra recentes + origem.
Filtra por tenant. Nao escreve.
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

cur.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_name='leads_prospectos' ORDER BY ordinal_position;""")
cols = [r[0] for r in cur.fetchall()]
print('Colunas leads_prospectos:', cols)

cur.execute("SELECT COUNT(*) FROM leads_prospectos WHERE tenant_id=12;")
print('\nTotal leads tenant 12:', cur.fetchone()[0])

# coluna de data
datacol = 'data_cadastro' if 'data_cadastro' in cols else ('criado_em' if 'criado_em' in cols else 'id')
origemcol = 'origem' if 'origem' in cols else None

cur.execute(f"""SELECT id, nome_razaosocial, telefone, {datacol}
               FROM leads_prospectos WHERE tenant_id=12 ORDER BY {datacol} DESC LIMIT 8;""")
print(f'\nLeads recentes (tenant 12, por {datacol}):')
for r in cur.fetchall():
    print(f'  id={r[0]} nome={r[1]!r} tel={r[2]} {datacol}={r[3]}')

if origemcol:
    cur.execute(f"""SELECT {origemcol}, COUNT(*) FROM leads_prospectos WHERE tenant_id=12
                   GROUP BY {origemcol} ORDER BY 2 DESC;""")
    print('\nPor origem:')
    for r in cur.fetchall():
        print(f'  {r[0]!r}: {r[1]}')

c.close()
