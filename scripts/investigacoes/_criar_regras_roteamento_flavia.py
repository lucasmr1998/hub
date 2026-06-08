"""Cria 3 regras de roteamento na TR Carrion (prod): cidade -> Flavia.

Faz INSERT em transacao explicita, verifica nao-duplicacao por nome,
mostra preview do que vai inserir e commita so depois.

ATENCAO: este script escreve em prod. Roda apenas uma vez.
"""
import psycopg2
import psycopg2.extras
from pathlib import Path

env_path = Path(__file__).resolve().parents[1] / '.env.prod_readonly'
env = {}
for line in env_path.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, v = line.split('=', 1)
    env[k.strip()] = v.strip()

# IMPORTANTE: este script faz INSERT, nao usa o user readonly se for diferente
conn = psycopg2.connect(
    host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
conn.autocommit = False  # transacao explicita
cur = conn.cursor()

TENANT_ID = 11   # TR Carrion
FLAVIA_ID = 23   # flavia.vidoto

REGRAS = [
    ('Roteamento Flavia — Palhoca',          'Palhoça'),
    ('Roteamento Flavia — Novo Hamburgo',    'Novo Hamburgo'),
    ('Roteamento Flavia — Francisco Beltrao','Francisco Beltrão'),
]

# Sanity checks
cur.execute("SELECT nome FROM sistema_tenant WHERE id = %s;", (TENANT_ID,))
row = cur.fetchone()
if not row:
    conn.rollback(); raise SystemExit(f'Tenant {TENANT_ID} nao existe')
print(f'Tenant: {row[0]}')

cur.execute("SELECT username, first_name, last_name FROM auth_user WHERE id = %s;", (FLAVIA_ID,))
row = cur.fetchone()
if not row:
    conn.rollback(); raise SystemExit(f'User {FLAVIA_ID} nao existe')
print(f'Usuario: {row[0]} ({row[1]} {row[2]})')

# Checa duplicacao por nome
nomes = [r[0] for r in REGRAS]
cur.execute(
    "SELECT id, nome FROM crm_regras_pipeline_estagio WHERE tenant_id = %s AND nome = ANY(%s);",
    (TENANT_ID, nomes),
)
existentes = cur.fetchall()
if existentes:
    print('\nJa existem regras com mesmo nome:')
    for r in existentes:
        print(f'  id={r[0]} nome="{r[1]}"')
    conn.rollback()
    raise SystemExit('Abortando para nao duplicar. Apague as antigas ou rode com nomes novos.')

# INSERT
import json
print('\nVai inserir:')
inseridos = []
for nome, cidade in REGRAS:
    condicoes = json.dumps([{'tipo': 'lead_campo', 'campo': 'cidade',
                              'operador': 'igual', 'valor': cidade}])
    acoes = json.dumps([{'tipo': 'atribuir_agente',
                          'config': {'user_id': FLAVIA_ID}}])
    cur.execute("""
        INSERT INTO crm_regras_pipeline_estagio
          (tenant_id, estagio_id, nome, condicoes, acoes, ativo, prioridade,
           total_disparos, criado_em, atualizado_em)
        VALUES (%s, NULL, %s, %s::jsonb, %s::jsonb, true, 1, 0, NOW(), NOW())
        RETURNING id;
    """, (TENANT_ID, nome, condicoes, acoes))
    rid = cur.fetchone()[0]
    inseridos.append((rid, nome, cidade))
    print(f'  id={rid} nome="{nome}" cidade="{cidade}"')

# Verifica
print('\nVerificando antes de commit:')
cur.execute("""
SELECT id, nome, condicoes, acoes, ativo
FROM crm_regras_pipeline_estagio
WHERE id = ANY(%s);
""", ([r[0] for r in inseridos],))
for r in cur.fetchall():
    print(f'  id={r[0]} nome="{r[1]}" ativo={r[4]}')
    print(f'    condicoes={r[2]}')
    print(f'    acoes={r[3]}')

conn.commit()
print('\nCOMMIT executado — 3 regras criadas.')
cur.close()
conn.close()
