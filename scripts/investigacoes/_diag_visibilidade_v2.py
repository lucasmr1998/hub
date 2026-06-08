"""Diagnostico v2: continua investigacao das conversas sem fila."""
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

print('==== EQUIPES E MEMBROS ====')
cur.execute("""
SELECT e.id, e.nome,
       array_agg(u.username) FILTER (WHERE u.id IS NOT NULL)
FROM inbox_equipes e
LEFT JOIN inbox_membros_equipe m ON m.equipe_id = e.id
LEFT JOIN auth_user u ON u.id = m.user_id
WHERE e.tenant_id = %s
GROUP BY e.id, e.nome;
""", (TID,))
for r in cur.fetchall():
    print(f'  equipe id={r[0]:3d} nome={r[1]!r}  membros={r[2]}')

print('\n==== Conversas com agente mas SEM FILA — quando foram criadas? ====')
cur.execute("""
SELECT c.id, c.contato_nome,
       u.username AS agente,
       c.modo_atendimento, c.status,
       c.data_abertura,
       (SELECT MIN(data_envio) FROM inbox_mensagens
         WHERE conversa_id = c.id AND remetente_tipo='contato') AS primeira_msg_cliente,
       (SELECT MIN(data_envio) FROM inbox_mensagens
         WHERE conversa_id = c.id AND remetente_tipo='agente') AS primeira_resp_agente
FROM inbox_conversas c
LEFT JOIN auth_user u ON u.id = c.agente_id
WHERE c.tenant_id = %s
  AND c.agente_id IS NOT NULL
  AND c.fila_id IS NULL
  AND c.status NOT IN ('arquivada','resolvida')
ORDER BY c.data_abertura DESC LIMIT 10;
""", (TID,))
for r in cur.fetchall():
    print(f'  c#{r[0]:4d} {(r[1] or "")[:18]:18s} agente={r[2] or "-":18s} '
          f'modo={r[3]:15s} abertura={str(r[5])[:16]} '
          f'1a_msg={str(r[6])[:16] if r[6] else "-":16s} '
          f'1a_resp={str(r[7])[:16] if r[7] else "-":16s}')

print('\n==== HISTORICO DE ATRIBUICAO — quanto tempo entre criacao da conversa e atribuicao do agente? ====')
cur.execute("""
SELECT c.id, c.contato_nome,
       c.data_abertura AS aberta_em,
       MIN(l.data_criacao) FILTER (WHERE l.acao = 'atribuir') AS atribuida_em,
       EXTRACT(EPOCH FROM (MIN(l.data_criacao) FILTER (WHERE l.acao = 'atribuir') - c.data_abertura))/60 AS minutos
FROM inbox_conversas c
LEFT JOIN log_sistema l ON l.entidade='conversa' AND l.entidade_id = c.id
                       AND l.tenant_id = c.tenant_id
WHERE c.tenant_id = %s
  AND c.data_abertura >= NOW() - INTERVAL '7 days'
  AND c.agente_id IS NOT NULL
GROUP BY c.id, c.contato_nome, c.data_abertura
HAVING MIN(l.data_criacao) FILTER (WHERE l.acao = 'atribuir') IS NOT NULL
ORDER BY minutos DESC LIMIT 15;
""", (TID,))
print('  conv | nome | abertura | atribuicao | delay (min)')
for r in cur.fetchall():
    nome = (r[1] or '')[:18]
    delay = r[4]
    print(f'  c#{r[0]:4d} {nome:18s} aberta={str(r[2])[:16]} atrib={str(r[3])[:16]} delay={delay:6.1f}min')

print('\n==== HISTORICO MUDANCAS DE MODO (signals do modo) — pra ver se modo muda tarde ====')
cur.execute("""
SELECT
  EXTRACT(EPOCH FROM (l.data_criacao - c.data_abertura))/60 AS minutos_apos_abertura,
  c.id, c.contato_nome, l.mensagem
FROM log_sistema l
JOIN inbox_conversas c ON c.id = l.entidade_id::int
WHERE l.tenant_id = %s
  AND l.entidade = 'conversa'
  AND l.mensagem ILIKE '%%modo%%'
  AND l.data_criacao >= NOW() - INTERVAL '7 days'
ORDER BY minutos_apos_abertura DESC LIMIT 10;
""", (TID,))
rows = cur.fetchall()
if rows:
    print('  delay | conv | nome | log')
    for r in rows:
        print(f'  {r[0]:6.1f}min  c#{r[1]:4d}  {(r[2] or "")[:15]:15s}  {(r[3] or "")[:60]}')
else:
    print('  (sem logs de mudanca de modo nos ultimos 7d)')

cur.close()
conn.close()
