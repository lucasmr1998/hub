"""Verifica o que esta cadastrado em viabilidade_cidadeviabilidade pra TR Carrion."""
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
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

print('CIDADES VIABILIDADE TR CARRION (tenant=11):')
cur.execute("""
SELECT id, cidade, estado, cep, bairro, ativo
FROM viabilidade_cidadeviabilidade
WHERE tenant_id = 11
ORDER BY cidade;
""")
rows = cur.fetchall()
print(f'  Total: {len(rows)}')
for r in rows:
    print(f'  id={r[0]:4d} {r[1]:35s} uf={r[2]:2s} cep={r[3] or "":10s} bairro={r[4] or "":20s} ativo={r[5]}')

print('\nQuantas cidades cadastradas POR TODOS os tenants?')
cur.execute("""
SELECT t.id, t.nome, COUNT(c.id) AS n_cidades
FROM sistema_tenant t
LEFT JOIN viabilidade_cidadeviabilidade c ON c.tenant_id = t.id
GROUP BY t.id, t.nome
ORDER BY n_cidades DESC;
""")
for r in cur.fetchall():
    print(f'  tenant={r[0]:3d} {r[1]:30s} cidades={r[2]}')

cur.close()
conn.close()
