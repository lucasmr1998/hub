"""Verifica: Flavia existe? Cidade esta sendo populada no Lead?"""
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
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()

TID = 11

print('USUARIOS TR CARRION (procura Flavia):')
cur.execute("""
SELECT u.id, u.username, u.first_name, u.last_name, u.is_active, u.date_joined
FROM auth_user u
JOIN sistema_permissao_usuario p ON p.user_id = u.id
WHERE p.tenant_id = %s
ORDER BY u.date_joined DESC;
""", (TID,))
for r in cur.fetchall():
    print(f'  id={r[0]:4d}  user={r[1]:25s}  nome="{r[2]} {r[3]}"  ativo={r[4]}  desde={str(r[5])[:10]}')

print('\nLEADS TR CARRION POR CIDADE (top 20 + procura por 3 cidades):')
cur.execute("""
SELECT cidade, estado, COUNT(*)
FROM leads_prospectos
WHERE tenant_id = %s
  AND cidade IS NOT NULL AND cidade <> ''
GROUP BY cidade, estado
ORDER BY count DESC
LIMIT 20;
""", (TID,))
print('  Top 20:')
for r in cur.fetchall():
    print(f'    cidade="{r[0]:30s}" uf="{r[1] or "":2s}" count={r[2]}')

print('\n  Procura especifica pelas 3 cidades:')
cur.execute("""
SELECT cidade, estado, COUNT(*)
FROM leads_prospectos
WHERE tenant_id = %s
  AND (
    cidade ILIKE '%%palhoca%%' OR cidade ILIKE '%%palhoça%%'
    OR cidade ILIKE '%%novo hamburgo%%' OR cidade ILIKE '%%nova hamburgo%%' OR cidade ILIKE '%%n hamburgo%%'
    OR cidade ILIKE '%%francisco beltrao%%' OR cidade ILIKE '%%francisco beltrão%%'
  )
GROUP BY cidade, estado
ORDER BY count DESC;
""", (TID,))
matches = cur.fetchall()
if matches:
    for r in matches:
        print(f'    cidade="{r[0]:30s}" uf="{r[1] or "":2s}" count={r[2]}')
else:
    print('    NENHUM LEAD encontrado com essas 3 cidades — pode estar com nome diferente')

print('\nLEADS ULTIMA SEMANA (sample com cidade preenchida):')
cur.execute("""
SELECT id, nome_razaosocial, cidade, estado, status_api, data_cadastro
FROM leads_prospectos
WHERE tenant_id = %s
  AND data_cadastro >= NOW() - INTERVAL '7 days'
ORDER BY data_cadastro DESC
LIMIT 15;
""", (TID,))
total_periodo = 0
com_cidade = 0
for r in cur.fetchall():
    total_periodo += 1
    if r[2]:
        com_cidade += 1
    print(f'  #{r[0]:5d} {(r[1] or "")[:25]:25s} cidade="{r[2] or "":20s}" uf="{r[3] or "":2s}" status={r[4] or "-":15s}')
print(f'  >>> {com_cidade}/{total_periodo} leads tem cidade preenchida')

print('\nESTAGIOS DO PIPELINE TR CARRION:')
cur.execute("""
SELECT pe.id, p.nome, pe.nome, pe.ordem, pe.is_final_ganho, pe.is_final_perdido, pe.ativo
FROM crm_pipeline_estagios pe
JOIN crm_pipelines p ON p.id = pe.pipeline_id
WHERE pe.tenant_id = %s
ORDER BY p.id, pe.ordem;
""", (TID,))
for r in cur.fetchall():
    flags = []
    if r[4]: flags.append('GANHO')
    if r[5]: flags.append('PERDIDO')
    if not r[6]: flags.append('INATIVO')
    print(f'  id={r[0]:4d}  pipeline="{r[1]:25s}"  estagio="{r[2]:25s}"  ordem={r[3]:3d}  {" ".join(flags)}')

cur.close()
conn.close()
