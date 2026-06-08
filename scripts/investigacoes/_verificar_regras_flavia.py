"""Verifica que as 3 regras estao ativas e visiveis pro engine."""
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

print('REGRAS DE ROTEAMENTO FLAVIA:')
cur.execute("""
SELECT id, nome, condicoes, acoes, ativo, total_disparos, ultima_execucao
FROM crm_regras_pipeline_estagio
WHERE id IN (16, 17, 18)
ORDER BY id;
""")
for r in cur.fetchall():
    print(f'  id={r[0]}  nome={r[1]!r}')
    print(f'    condicoes={r[2]}')
    print(f'    acoes={r[3]}')
    print(f'    ativo={r[4]}  disparos={r[5]}  ultima={r[6]}')

print('\nERROS RECENTES DO MOTOR (categoria=crm, ultimas 2h):')
cur.execute("""
SELECT data_criacao, acao, mensagem
FROM log_sistema
WHERE tenant_id = 11
  AND categoria = 'crm'
  AND data_criacao >= NOW() - INTERVAL '2 hours'
ORDER BY data_criacao DESC
LIMIT 20;
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        msg = (r[2] or '')[:80]
        print(f'  {str(r[0])[:19]} {r[1]:20s} {msg}')
else:
    print('  (sem logs categoria=crm nas ultimas 2h)')

print('\nOPORTUNIDADES TR CARRION COM CIDADE NAS 3 DAS REGRAS:')
cur.execute("""
SELECT o.id, l.nome_razaosocial, l.cidade, o.responsavel_id, e.nome AS estagio
FROM crm_oportunidades o
JOIN leads_prospectos l ON l.id = o.lead_id
LEFT JOIN crm_pipeline_estagios e ON e.id = o.estagio_id
WHERE o.tenant_id = 11
  AND o.ativo = true
  AND l.cidade IN ('Palhoça','Novo Hamburgo','Francisco Beltrão',
                    'Palhoca','Francisco Beltrao');
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f'  oport={r[0]} lead="{r[1]}" cidade={r[2]!r} resp={r[3]} estagio="{r[4]}"')
else:
    print('  (zero oport com leads das 3 cidades — esperado, vai chegar quando comecar)')

cur.close()
conn.close()
