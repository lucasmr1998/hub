"""Auditoria: clientes que enviaram imagem/documento no chat mas nao foram
persistidos em imagens_lead_prospecto (Hubtrix)."""
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

print('=== IMAGENS ENVIADAS PELO CLIENTE (chat) vs REGISTRADAS (cadastro) ===\n')
cur.execute("""
SELECT
  c.id AS conv, c.contato_nome, c.contato_telefone, c.lead_id,
  COUNT(m.id) AS imgs_no_chat,
  MIN(m.data_envio) AS primeira,
  MAX(m.data_envio) AS ultima,
  COALESCE((SELECT COUNT(*) FROM imagens_lead_prospecto i
            WHERE i.lead_id = c.lead_id), 0) AS imgs_registradas,
  COUNT(m.arquivo_url) FILTER (WHERE m.arquivo_url <> '') AS com_url
FROM inbox_conversas c
JOIN inbox_mensagens m ON m.conversa_id = c.id
WHERE c.tenant_id = %s
  AND m.remetente_tipo = 'contato'
  AND m.tipo_conteudo IN ('imagem', 'arquivo', 'video')
GROUP BY c.id, c.contato_nome, c.contato_telefone, c.lead_id
ORDER BY c.id DESC;
""", (TID,))
rows = cur.fetchall()
perdidos = []
print(f'{"conv":>5} {"cliente":20s} {"telefone":14s} {"chat":>4} {"reg":>4} {"url":>4}  status')
for r in rows:
    conv, nome, tel, lead, chat, prim, ult, reg, com_url = r
    if reg < chat:
        status = 'PERDIDO' if reg == 0 else 'PARCIAL'
        perdidos.append(r)
    else:
        status = 'ok'
    nome_s = (nome or '')[:20]
    print(f'{conv:>5} {nome_s:20s} {tel:14s} {chat:>4} {reg:>4} {com_url:>4}  {status}')

print(f'\n>>> Total conversas com imagem no chat: {len(rows)}')
print(f'>>> Com documento PERDIDO/PARCIAL: {len(perdidos)}')

print('\n=== DETALHE DOS PERDIDOS (com URL pra eventual recuperacao) ===')
for r in perdidos:
    conv = r[0]
    print(f'\n  conv #{conv} — {(r[1] or "")[:25]} ({r[2]}) lead={r[3]} | chat={r[4]} registradas={r[7]}')
    cur.execute("""
        SELECT data_envio, tipo_conteudo, arquivo_url, arquivo_nome
        FROM inbox_mensagens
        WHERE conversa_id = %s AND remetente_tipo='contato'
          AND tipo_conteudo IN ('imagem','arquivo','video')
        ORDER BY data_envio;
    """, (conv,))
    for m in cur.fetchall():
        url = (m[2] or '')[:60]
        print(f'      {str(m[0])[:19]} {m[1]:8s} url={url!r} nome={m[3]!r}')

cur.close()
conn.close()
