"""Acha duplicatas no cadastro (mesma cidade com/sem acento, etc.)."""
import sys
import unicodedata
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


def strip_accents(s):
    return ''.join(
        c for c in unicodedata.normalize('NFD', s or '')
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


conn = psycopg2.connect(
    host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

cur.execute("""
SELECT id, cidade, estado, data_criacao
FROM viabilidade_cidadeviabilidade
WHERE tenant_id = 11
ORDER BY cidade;
""")
rows = cur.fetchall()
print(f'Total: {len(rows)}')

# Agrupa por (cidade_norm, estado_norm)
grupos = {}
for r in rows:
    key = (strip_accents(r[1]), strip_accents(r[2]))
    grupos.setdefault(key, []).append(r)

print('\nDUPLICATAS:')
for key, lista in sorted(grupos.items()):
    if len(lista) > 1:
        print(f'  key={key}:')
        for r in lista:
            print(f'    id={r[0]:4d} cidade={r[1]!r} estado={r[2]!r} criado={r[3]}')

cur.close()
conn.close()
