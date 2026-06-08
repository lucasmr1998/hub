"""Backfill: atribui fila padrao do tenant pras conversas ativas em modo
humano/finalizado_bot que ficaram sem fila por causa do bug do modo_mudou.

Idempotente: SO mexe em conversas com fila=NULL.
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

try:
    # Pega fila padrao do tenant
    cur.execute("""
        SELECT id, nome, equipe_id FROM inbox_filas
        WHERE tenant_id = %s AND ativo = TRUE
        ORDER BY prioridade DESC LIMIT 1;
    """, (TID,))
    row = cur.fetchone()
    if not row:
        raise SystemExit('Nao ha fila ativa no tenant 11')
    fila_id, fila_nome, equipe_id = row
    print(f'Fila padrao: id={fila_id} nome={fila_nome!r} equipe={equipe_id}')

    # Conta antes
    cur.execute("""
        SELECT COUNT(*) FROM inbox_conversas
        WHERE tenant_id = %s AND fila_id IS NULL
          AND modo_atendimento IN ('humano','finalizado_bot')
          AND status NOT IN ('arquivada','resolvida');
    """, (TID,))
    n_antes = cur.fetchone()[0]
    print(f'Conversas sem fila (vao ser atualizadas): {n_antes}')

    # Lista antes pra log
    cur.execute("""
        SELECT id, contato_nome, modo_atendimento, agente_id
        FROM inbox_conversas
        WHERE tenant_id = %s AND fila_id IS NULL
          AND modo_atendimento IN ('humano','finalizado_bot')
          AND status NOT IN ('arquivada','resolvida')
        ORDER BY data_abertura DESC;
    """, (TID,))
    for r in cur.fetchall():
        print(f'  c#{r[0]:4d} {(r[1] or "")[:25]:25s} modo={r[2]:15s} agente_id={r[3]}')

    # UPDATE em lote
    cur.execute("""
        UPDATE inbox_conversas
        SET fila_id = %s, equipe_id = %s
        WHERE tenant_id = %s AND fila_id IS NULL
          AND modo_atendimento IN ('humano','finalizado_bot')
          AND status NOT IN ('arquivada','resolvida');
    """, (fila_id, equipe_id, TID))
    print(f'\nUPDATE: rows={cur.rowcount}')

    # Conta depois
    cur.execute("""
        SELECT COUNT(*) FROM inbox_conversas
        WHERE tenant_id = %s AND fila_id IS NULL
          AND modo_atendimento IN ('humano','finalizado_bot')
          AND status NOT IN ('arquivada','resolvida');
    """, (TID,))
    print(f'Conversas sem fila apos: {cur.fetchone()[0]}')

    conn.commit()
    print('COMMIT.')
finally:
    cur.close()
    conn.close()
