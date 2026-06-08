"""Lista colunas da tabela crm_configuracao em prod."""
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')
conn = psycopg2.connect(
    host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
    database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'crm_configuracao'
    ORDER BY ordinal_position;
""")
for row in cur.fetchall():
    print(f'  {row[0]:42} {row[1]:30} nullable={row[2]:5}  default={row[3]}')
cur.close()
conn.close()
