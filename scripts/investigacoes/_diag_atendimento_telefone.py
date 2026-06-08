"""Diagnostica por que o bot parou de responder um atendimento especifico."""
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
TEL = '5514996116561'

print('==== CONVERSA(S) DO TELEFONE ====')
cur.execute("""
SELECT c.id, c.contato_nome, c.contato_telefone, c.status, c.modo_atendimento,
       c.agente_id, u.username, c.fila_id, c.data_abertura, c.ultima_mensagem_em,
       c.lead_id, c.oportunidade_id
FROM inbox_conversas c
LEFT JOIN auth_user u ON u.id = c.agente_id
WHERE c.tenant_id = %s
  AND (c.contato_telefone LIKE %s OR c.contato_telefone LIKE %s)
ORDER BY c.data_abertura DESC;
""", (TID, f'%{TEL}%', f'%{TEL[2:]}%'))
convs = cur.fetchall()
for r in convs:
    print(f'  c#{r[0]} nome={r[1]!r} tel={r[2]!r}')
    print(f'    status={r[3]} modo={r[4]} agente={r[6] or r[5]} fila={r[7]}')
    print(f'    abertura={r[8]} ult_msg={r[9]} lead={r[10]} oport={r[11]}')

if not convs:
    print('  NENHUMA conversa encontrada com esse telefone')
    cur.close(); conn.close(); sys.exit()

conv_id = convs[0][0]
oport_id = convs[0][11]

print(f'\n==== ULTIMAS 20 MENSAGENS DA CONVERSA #{conv_id} ====')
cur.execute("""
SELECT data_envio, remetente_tipo, remetente_nome, tipo_conteudo,
       LEFT(conteudo, 70)
FROM inbox_mensagens
WHERE conversa_id = %s
ORDER BY data_envio DESC LIMIT 20;
""", (conv_id,))
for r in cur.fetchall():
    print(f'  {str(r[0])[:19]} [{r[1]:7s}] {(r[2] or "")[:12]:12s} ({r[3]}) {(r[4] or "").strip()}')

print(f'\n==== OPORTUNIDADE / atendimento_estado (dados_custom) ====')
if oport_id:
    cur.execute("SELECT dados_custom, estagio_id FROM crm_oportunidades WHERE id = %s;", (oport_id,))
    r = cur.fetchone()
    if r:
        print(f'  estagio_id={r[1]}')
        print(f'  dados_custom={r[0]}')

print(f'\n==== LOGS DA CONVERSA (categoria inbox/crm/integracao, ultimos 3 dias) ====')
cur.execute("""
SELECT data_criacao, categoria, acao, LEFT(mensagem, 70)
FROM log_sistema
WHERE tenant_id = %s
  AND ((entidade='conversa' AND entidade_id = %s)
       OR (entidade='oportunidade' AND entidade_id = %s))
  AND data_criacao >= NOW() - INTERVAL '3 days'
ORDER BY data_criacao DESC LIMIT 30;
""", (TID, conv_id, oport_id or 0))
for r in cur.fetchall():
    print(f'  {str(r[0])[:19]} [{r[1]:10s}] {r[2]:18s} {(r[3] or "").strip()}')

cur.close()
conn.close()
