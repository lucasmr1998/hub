"""Query read-only TR Carrion atendimentos. Carrega creds de .env.prod_readonly."""
import sys
import psycopg2
from pathlib import Path

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
    password=env['PROD_DB_PASSWORD'],
    connect_timeout=10,
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

cur.execute("SELECT id, nome, slug FROM sistema_tenant WHERE slug ILIKE %s OR nome ILIKE %s LIMIT 5;",
            ('%carrion%', '%carrion%'))
tenants = cur.fetchall()
print('TENANTS:')
for t in tenants:
    print(f'  id={t[0]}  nome={t[1]!r}  slug={t[2]!r}')
if not tenants:
    sys.exit('Nenhum tenant carrion')

tid = tenants[0][0]

print('\nCONVERSAS ULTIMOS 7 DIAS:')
cur.execute("""
SELECT
  c.id, c.contato_nome, c.status, c.modo_atendimento, c.agente_id,
  c.ultima_mensagem_em, c.mensagens_nao_lidas,
  (SELECT COUNT(*) FROM inbox_mensagens WHERE conversa_id = c.id) AS total,
  (SELECT COUNT(*) FROM inbox_mensagens WHERE conversa_id = c.id AND remetente_tipo='contato') AS contato,
  (SELECT COUNT(*) FROM inbox_mensagens WHERE conversa_id = c.id AND remetente_tipo='bot') AS bot,
  (SELECT COUNT(*) FROM inbox_mensagens WHERE conversa_id = c.id AND remetente_tipo='agente') AS agente,
  o.id, o.estagio_id, o.titulo
FROM inbox_conversas c
LEFT JOIN crm_oportunidades o ON o.id = c.oportunidade_id
WHERE c.tenant_id = %s
  AND c.data_abertura >= NOW() - INTERVAL '7 days'
ORDER BY c.ultima_mensagem_em DESC NULLS LAST
LIMIT 50;
""", (tid,))
rows = cur.fetchall()
print(f'  {len(rows)} conversas')
for r in rows:
    (cid, nome, status, modo, agente, ult, nl, tot, ctt, bt, ag, oid, eid, ot) = r
    nome_s = (nome or '')[:25]
    print(f'  #{cid:6d} {nome_s:25s} status={status:11s} modo={modo or "-":12s} '
          f'agente={agente or "-":>4} ult={str(ult)[:16]} nl={nl} '
          f'tot={tot} c={ctt} b={bt} a={ag} oport={oid or "-"} estagio={eid or "-"}')

print('\nAGENTES DISTRIBUIDOS NAS CONVERSAS DO PERIODO:')
cur.execute("""
SELECT u.id, u.username, u.first_name || ' ' || u.last_name AS nome,
       COUNT(*) AS conversas
FROM inbox_conversas c
JOIN auth_user u ON u.id = c.agente_id
WHERE c.tenant_id = %s
  AND c.data_abertura >= NOW() - INTERVAL '7 days'
GROUP BY u.id, u.username, u.first_name, u.last_name
ORDER BY conversas DESC;
""", (tid,))
for r in cur.fetchall():
    print(f'  agente={r[0]} user={r[1]} nome={r[2]} conversas={r[3]}')

print('\nSTATUS DISTRIBUTION (TODAS):')
cur.execute("""
SELECT status, modo_atendimento, COUNT(*)
FROM inbox_conversas
WHERE tenant_id = %s
GROUP BY status, modo_atendimento
ORDER BY count DESC;
""", (tid,))
for r in cur.fetchall():
    print(f'  status={r[0]:12s} modo={r[1] or "-":15s} count={r[2]}')

print('\nOPORTUNIDADES POR ESTAGIO (ULTIMOS 30 DIAS):')
cur.execute("""
SELECT e.nome, COUNT(*)
FROM crm_oportunidades o
LEFT JOIN crm_pipeline_estagios e ON e.id = o.estagio_id
WHERE o.tenant_id = %s
  AND o.data_criacao >= NOW() - INTERVAL '30 days'
GROUP BY e.nome
ORDER BY count DESC;
""", (tid,))
for r in cur.fetchall():
    print(f'  estagio={r[0] or "(sem estagio)":30s} count={r[1]}')

print('\nLOGS RECENTES (24h):')
cur.execute("""
SELECT data_criacao, categoria, acao, entidade, entidade_id, mensagem
FROM log_sistema
WHERE tenant_id = %s
  AND data_criacao >= NOW() - INTERVAL '24 hours'
ORDER BY data_criacao DESC
LIMIT 30;
""", (tid,))
for r in cur.fetchall():
    msg = (r[5] or '')[:60]
    print(f'  {str(r[0])[:19]} {r[1]:12s} {r[2]:20s} {r[3]:15s} id={r[4] or "-"} {msg}')

cur.close()
conn.close()
