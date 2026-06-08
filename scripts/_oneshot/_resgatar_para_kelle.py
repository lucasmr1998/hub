"""Resgata conversas travadas (estado undefined) passando pra Kelle (id 21):
modo=humano, agente=Kelle, fila=8. So mexe nas abertas. Transacional.
"""
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

TID = 11
KELLE = 21
FILA = 8

# Conversas alvo (abertas com estado undefined / bot mudo)
ALVOS = [285, 281, 279]  # Ailton, Sandra, Gustavo (Rafael #255 esta resolvida)

try:
    # Estado antes
    print('ANTES:')
    cur.execute("""
        SELECT c.id, c.contato_nome, c.status, c.modo_atendimento,
               c.agente_id, u.username, c.fila_id, c.oportunidade_id
        FROM inbox_conversas c
        LEFT JOIN auth_user u ON u.id = c.agente_id
        WHERE c.tenant_id = %s AND c.id = ANY(%s)
        ORDER BY c.id;
    """, (TID, ALVOS))
    rows = cur.fetchall()
    for r in rows:
        print(f'  c#{r[0]} {(r[1] or "")[:18]:18s} status={r[2]:10s} modo={r[3]:13s} '
              f'agente={r[5] or r[4]} fila={r[6]} oport={r[7]}')

    abertas = [r[0] for r in rows if r[2] == 'aberta']
    oports = [r[7] for r in rows if r[2] == 'aberta' and r[7]]

    if not abertas:
        print('\nNenhuma aberta pra resgatar.')
        conn.rollback(); sys.exit()

    # UPDATE: passa pra Kelle, modo humano, fila padrao
    cur.execute("""
        UPDATE inbox_conversas
        SET agente_id = %s, modo_atendimento = 'humano',
            fila_id = COALESCE(fila_id, %s),
            equipe_id = COALESCE(equipe_id, (SELECT equipe_id FROM inbox_filas WHERE id = %s))
        WHERE tenant_id = %s AND id = ANY(%s);
    """, (KELLE, FILA, FILA, TID, abertas))
    print(f'\nUPDATE conversas: {cur.rowcount}')

    # Atribui responsavel da oportunidade tambem (se vazio)
    if oports:
        cur.execute("""
            UPDATE crm_oportunidades
            SET responsavel_id = COALESCE(responsavel_id, %s)
            WHERE tenant_id = %s AND id = ANY(%s);
        """, (KELLE, TID, oports))
        print(f'UPDATE oportunidades (responsavel): {cur.rowcount}')

    # Estado depois
    print('\nDEPOIS:')
    cur.execute("""
        SELECT c.id, c.contato_nome, c.status, c.modo_atendimento,
               u.username, c.fila_id
        FROM inbox_conversas c
        LEFT JOIN auth_user u ON u.id = c.agente_id
        WHERE c.tenant_id = %s AND c.id = ANY(%s)
        ORDER BY c.id;
    """, (TID, ALVOS))
    for r in cur.fetchall():
        print(f'  c#{r[0]} {(r[1] or "")[:18]:18s} status={r[2]:10s} modo={r[3]:13s} '
              f'agente={r[4]} fila={r[5]}')

    conn.commit()
    print('\nCOMMIT.')
finally:
    cur.close()
    conn.close()
