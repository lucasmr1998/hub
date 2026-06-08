"""READ-ONLY prod: cidades dos leads do tenant 12 (Nuvyon). Indicador de cobertura.
Mostra cidade/UF com contagem e quantos viraram cliente (id_hubsoft preenchido).
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
cur.execute("""SELECT COALESCE(NULLIF(cidade,''),'(vazio)') AS cidade,
                      COALESCE(estado,'') AS uf,
                      COUNT(*) AS leads,
                      COUNT(id_hubsoft) AS com_hubsoft
               FROM leads_prospectos WHERE tenant_id=12
               GROUP BY 1,2 ORDER BY leads DESC;""")
print('Cidades dos leads (tenant 12 = Nuvyon):')
print('  cidade / UF | leads | com_hubsoft')
for r in cur.fetchall():
    print(f'  {r[0]} / {r[1]} | {r[2]} | {r[3]}')
c.close()
