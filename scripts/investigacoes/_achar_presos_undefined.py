"""Acha conversas TR Carrion presas: bot mudo apos cliente, ou
atendimento_estado='undefined'."""
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

print('==== OPORTUNIDADES COM atendimento_estado = undefined ====')
cur.execute("""
SELECT o.id, l.nome_razaosocial, l.telefone, o.dados_custom->>'atendimento_estado',
       o.dados_custom->>'atendimento_atualizado_em'
FROM crm_oportunidades o
JOIN leads_prospectos l ON l.id = o.lead_id
WHERE o.tenant_id = %s
  AND o.dados_custom->>'atendimento_estado' = 'undefined'
ORDER BY o.dados_custom->>'atendimento_atualizado_em' DESC;
""", (TID,))
rows = cur.fetchall()
print(f'Total: {len(rows)}')
for r in rows:
    print(f'  oport={r[0]} {(r[1] or "")[:22]:22s} tel={r[2]} estado={r[3]} em={r[4]}')

print('\n==== CONVERSAS modo=bot, aberta, ULTIMA MSG do CONTATO (bot ficou mudo) ====')
cur.execute("""
SELECT c.id, c.contato_nome, c.contato_telefone, c.ultima_mensagem_em,
       m.remetente_tipo AS ult_remetente,
       EXTRACT(EPOCH FROM (NOW() - c.ultima_mensagem_em))/3600 AS horas_parado
FROM inbox_conversas c
JOIN LATERAL (
    SELECT remetente_tipo FROM inbox_mensagens
    WHERE conversa_id = c.id ORDER BY data_envio DESC LIMIT 1
) m ON true
WHERE c.tenant_id = %s
  AND c.modo_atendimento = 'bot'
  AND c.status = 'aberta'
  AND m.remetente_tipo = 'contato'
ORDER BY c.ultima_mensagem_em DESC;
""", (TID,))
rows = cur.fetchall()
print(f'Total presos (cliente falou, bot mudo): {len(rows)}')
for r in rows:
    print(f'  c#{r[0]:4d} {(r[1] or "")[:20]:20s} tel={r[2]:14s} '
          f'ult={str(r[3])[:16]} parado_ha={r[5]:.1f}h')

cur.close()
conn.close()
