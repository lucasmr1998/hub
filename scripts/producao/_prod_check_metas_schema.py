"""READ-ONLY prod: compara colunas de crm_metas_vendas (e tabelas relacionadas)
com o que o model espera, pra achar migration faltando. Tambem checa django_migrations
pendentes do app crm. Nao escreve."""
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

esperado = {'id','tipo','vendedor_id','equipe_id','periodo','data_inicio','data_fim',
    'meta_vendas_quantidade','meta_vendas_valor','meta_leads_qualificados','meta_contatos',
    'realizado_vendas_quantidade','realizado_vendas_valor','realizado_leads',
    'criado_por_id','data_criacao','tenant_id'}

cur.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_name='crm_metas_vendas';""")
reais = {r[0] for r in cur.fetchall()}
print('crm_metas_vendas existe:', bool(reais))
print('colunas reais:', sorted(reais))
print('FALTANDO em prod (model espera, prod nao tem):', sorted(esperado - reais))
print('SOBRANDO em prod (prod tem, model nao lista):', sorted(reais - esperado))

# migrations do crm aplicadas
cur.execute("""SELECT name FROM django_migrations WHERE app='crm' ORDER BY id DESC LIMIT 8;""")
print('\nultimas migrations crm aplicadas em prod:')
for (nm,) in cur.fetchall():
    print('  ', nm)
c.close()
