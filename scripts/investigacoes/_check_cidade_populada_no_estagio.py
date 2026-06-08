"""Verifica: leads que chegaram em Aguardando Vendedor (ou avancaram) tem cidade?"""
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
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

TID = 11

print('CIDADE POR ESTAGIO (todas oportunidades ativas):')
cur.execute("""
SELECT
  pe.nome AS estagio,
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE l.cidade IS NULL OR l.cidade = '') AS sem_cidade,
  COUNT(*) FILTER (WHERE l.cidade IS NOT NULL AND l.cidade <> '') AS com_cidade,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE l.cidade IS NOT NULL AND l.cidade <> '')
    / NULLIF(COUNT(*), 0),
    1
  ) AS pct_com_cidade
FROM crm_oportunidades o
JOIN crm_pipeline_estagios pe ON pe.id = o.estagio_id
LEFT JOIN leads_prospectos l ON l.id = o.lead_id
WHERE o.tenant_id = %s AND o.ativo = true
GROUP BY pe.nome, pe.ordem
ORDER BY pe.ordem;
""", (TID,))
for r in cur.fetchall():
    print(f'  estagio={r[0]:25s} total={r[1]:3d}  sem={r[2]:3d}  com={r[3]:3d}  pct={r[4] or "—"}%')

print('\nLEADS DENTRO DE "Em Negociacao" (estagio 53) — onde estao todos os 26:')
cur.execute("""
SELECT l.id, l.nome_razaosocial, l.cidade, l.estado, l.cep
FROM crm_oportunidades o
JOIN leads_prospectos l ON l.id = o.lead_id
WHERE o.tenant_id = %s AND o.estagio_id = 53 AND o.ativo = true
ORDER BY o.data_atualizacao DESC
LIMIT 15;
""", (TID,))
for r in cur.fetchall():
    nome = (r[1] or '')[:25]
    cid = (r[2] or '')[:25]
    print(f'  #{r[0]:4d} {nome:25s}  cidade="{cid:25s}" uf="{r[3] or "":2s}" cep="{r[4] or "":10s}"')

print('\nTODAS as cidades cadastradas (distinct) com count:')
cur.execute("""
SELECT cidade, COUNT(*) FROM leads_prospectos
WHERE tenant_id = %s
GROUP BY cidade ORDER BY count DESC;
""", (TID,))
for r in cur.fetchall():
    print(f'  cidade="{(r[0] or "(NULL)"):30s}" count={r[1]}')

cur.close()
conn.close()
