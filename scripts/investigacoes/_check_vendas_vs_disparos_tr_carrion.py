"""Diagnostica gap: 29 disparos da regra Criar Venda vs poucas vendas cadastradas."""
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

print('REGRA "Docs recebidos -> Criar Venda" e similares:')
cur.execute("""
SELECT id, nome, condicoes, acoes, total_disparos, ultima_execucao
FROM crm_regras_pipeline_estagio
WHERE tenant_id = %s
  AND acoes::text ILIKE '%%criar_venda%%';
""", (TID,))
for r in cur.fetchall():
    print(f'  id={r[0]} nome={r[1]!r} disparos={r[4]} ultima={r[5]}')
    print(f'    condicoes={r[2]}')
    print(f'    acoes={r[3]}')

print('\nTABELAS DE VENDA — quantas existem?')
cur.execute("""
SELECT COUNT(*), MIN(data_venda), MAX(data_venda)
FROM crm_vendas WHERE tenant_id = %s;
""", (TID,))
r = cur.fetchone()
print(f'  Total Vendas: {r[0]}  (primeira={r[1]} ultima={r[2]})')

print('\nVENDAS POR STATUS:')
cur.execute("SELECT status, COUNT(*) FROM crm_vendas WHERE tenant_id = %s GROUP BY status;", (TID,))
for r in cur.fetchall():
    print(f'  status={r[0]!r} count={r[1]}')

print('\nULTIMAS 10 VENDAS:')
cur.execute("""
SELECT v.id, v.status, v.oportunidade_id, v.valor, v.data_venda, l.nome_razaosocial
FROM crm_vendas v
LEFT JOIN crm_oportunidades o ON o.id = v.oportunidade_id
LEFT JOIN leads_prospectos l ON l.id = o.lead_id
WHERE v.tenant_id = %s
ORDER BY v.data_venda DESC LIMIT 10;
""", (TID,))
for r in cur.fetchall():
    print(f'  v#{r[0]} status={r[1]!r} oport={r[2]} valor={r[3]} data={str(r[4])[:19]} lead={r[5]!r}')

print('\nOPORTUNIDADES COM IMAGEM/DOCUMENTO STATUS=validado (que satisfazem a condicao):')
cur.execute("""
SELECT DISTINCT i.lead_id, l.nome_razaosocial, COUNT(i.id) AS imgs, o.id AS oport_id,
       (SELECT EXISTS (SELECT 1 FROM crm_vendas WHERE oportunidade_id = o.id)) AS tem_venda
FROM imagens_lead_prospecto i
JOIN leads_prospectos l ON l.id = i.lead_id
JOIN crm_oportunidades o ON o.lead_id = i.lead_id
WHERE i.tenant_id = %s
GROUP BY i.lead_id, l.nome_razaosocial, o.id
ORDER BY imgs DESC LIMIT 15;
""", (TID,))
for r in cur.fetchall():
    print(f'  lead={r[0]} nome={r[1]!r} imgs={r[2]} oport={r[3]} tem_venda={r[4]}')

cur.close()
conn.close()
