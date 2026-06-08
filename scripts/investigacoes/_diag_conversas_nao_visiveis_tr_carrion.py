"""Diagnostico: por que vendedoras nao veem todas as conversas nao atribuidas.

Regra critica em apps/inbox/views.py:119-126: agente comum so ve conversa
nao atribuida se ela tiver FILA da equipe dele. Se fila=NULL, invisivel.
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
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

TID = 11

print('==== CONVERSAS POR (agente, fila, modo) — situacao atual ====')
cur.execute("""
SELECT
  CASE WHEN agente_id IS NULL THEN 'sem agente' ELSE 'com agente' END AS agente,
  CASE WHEN fila_id IS NULL THEN 'SEM FILA' ELSE 'com fila' END AS fila,
  modo_atendimento, status, COUNT(*)
FROM inbox_conversas
WHERE tenant_id = %s AND status NOT IN ('arquivada','resolvida')
GROUP BY 1, 2, modo_atendimento, status
ORDER BY 5 DESC;
""", (TID,))
for r in cur.fetchall():
    print(f'  agente={r[0]:11s} fila={r[1]:9s} modo={r[2] or "-":15s} status={r[3]:10s} count={r[4]}')

print('\n==== CONVERSAS SEM AGENTE E SEM FILA (invisiveis pras vendedoras) ====')
cur.execute("""
SELECT c.id, c.contato_nome, c.modo_atendimento, c.status,
       c.data_abertura, c.ultima_mensagem_em,
       c.mensagens_nao_lidas,
       l.cidade
FROM inbox_conversas c
LEFT JOIN leads_prospectos l ON l.id = c.lead_id
WHERE c.tenant_id = %s
  AND c.agente_id IS NULL
  AND c.fila_id IS NULL
  AND c.status NOT IN ('arquivada','resolvida')
ORDER BY c.data_abertura DESC LIMIT 30;
""", (TID,))
for r in cur.fetchall():
    nome = (r[1] or '')[:20]
    print(f'  c#{r[0]:4d} {nome:20s} modo={r[2] or "-":15s} status={r[3]:10s} '
          f'aberto={str(r[4])[:16]} ult={str(r[5])[:16] if r[5] else "NULL":16s} '
          f'cidade={r[7] or "":15s}')

print('\n==== FILAS ATIVAS DO TENANT ====')
cur.execute("""
SELECT id, nome, equipe_id, prioridade, ativo
FROM inbox_filas
WHERE tenant_id = %s;
""", (TID,))
for r in cur.fetchall():
    print(f'  fila id={r[0]:3d} nome={r[1]!r} equipe={r[2]} prio={r[3]} ativo={r[4]}')

print('\n==== EQUIPES E MEMBROS ====')
cur.execute("""
SELECT e.id, e.nome,
       (SELECT array_agg(u.username) FROM inbox_equipes_membros m
        JOIN auth_user u ON u.id = m.user_id WHERE m.equipe_id = e.id)
FROM inbox_equipes e
WHERE e.tenant_id = %s;
""", (TID,))
for r in cur.fetchall():
    print(f'  equipe id={r[0]:3d} nome={r[1]!r} membros={r[2]}')

print('\n==== TEMPO ENTRE ABERTURA E ATRIBUICAO DE FILA (historico) ====')
print('(quero saber se historicamente teve delay)')
cur.execute("""
WITH base AS (
  SELECT c.id, c.contato_nome, c.modo_atendimento, c.data_abertura, c.fila_id,
         (SELECT MIN(timestamp) FROM log_sistema
          WHERE tenant_id = %s AND entidade='conversa' AND entidade_id = c.id
            AND mensagem ILIKE '%%modo%%') AS primeira_msg_modo
  FROM inbox_conversas c
  WHERE c.tenant_id = %s
    AND c.data_abertura >= NOW() - INTERVAL '7 days'
)
SELECT COUNT(*) FILTER (WHERE fila_id IS NULL) AS sem_fila,
       COUNT(*) FILTER (WHERE fila_id IS NOT NULL) AS com_fila,
       COUNT(*)
FROM base;
""", (TID, TID))
r = cur.fetchone()
print(f'  Ultimos 7 dias: total={r[2]}  com fila={r[1]}  SEM fila={r[0]}')

cur.close()
conn.close()
