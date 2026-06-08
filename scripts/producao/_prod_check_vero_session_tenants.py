"""READ-ONLY: checa estrutura da vero_session em prod e distribuicao por tenant.
Risco: se o fluxo de follow-up roda sem filtro de tenant e ha sessoes de outros
tenants alem da TR Carrion, manda WhatsApp errado."""
import sys
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
from pathlib import Path

env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
cur = c.cursor()

print('=== colunas da vero_session ===')
cur.execute("""SELECT column_name, data_type FROM information_schema.columns
WHERE table_name='vero_session' ORDER BY ordinal_position;""")
cols = cur.fetchall()
for n, t in cols:
    print(f'  {n}: {t}')
tem_tenant = any(n == 'tenant_id' for n, _ in cols)
print(f'\ntem tenant_id? {tem_tenant}')

print('\n=== contagem total + por mes ===')
cur.execute("SELECT COUNT(*) FROM vero_session;")
print('total:', cur.fetchone()[0])

if tem_tenant:
    print('\n=== distribuicao por tenant ===')
    cur.execute("""SELECT vs.tenant_id, t.slug, t.nome, COUNT(*)
        FROM vero_session vs LEFT JOIN sistema_tenant t ON t.id=vs.tenant_id
        GROUP BY vs.tenant_id, t.slug, t.nome ORDER BY COUNT(*) DESC;""")
    for tid, slug, nome, n in cur.fetchall():
        print(f'  tenant_id={tid} slug={slug!r} nome={nome!r} sessoes={n}')

print('\n=== sessoes recentes (ultimas 24h) ===')
cur.execute("""SELECT """ + ('tenant_id, ' if tem_tenant else '') + """COUNT(*)
FROM vero_session WHERE atualizado_em > NOW() - INTERVAL '24 hours'
""" + ('GROUP BY tenant_id ORDER BY COUNT(*) DESC' if tem_tenant else ''))
for r in cur.fetchall():
    print(' ', r)

print('\n=== amostra (3 linhas mais recentes) ===')
cur.execute("""SELECT """ + ('tenant_id, ' if tem_tenant else '') + """telefone, nodo_atual, atualizado_em
FROM vero_session ORDER BY atualizado_em DESC LIMIT 3;""")
for r in cur.fetchall():
    print(' ', r)
c.close()
