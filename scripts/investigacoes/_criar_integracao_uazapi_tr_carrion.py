"""
Cria IntegracaoAPI Uazapi pro tenant tr-carrion e linka ao CanalInbox Vero WhatsApp.

PROD WRITE — autorizado pelo usuario.
"""
import json
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')
conn = psycopg2.connect(host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
                         database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
                         password=env['PROD_DB_PASSWORD'], connect_timeout=10)
conn.autocommit = False
cur = conn.cursor()

TENANT_ID = 11
CANAL_ID = 13
UAZAPI_URL = 'https://consulteplus.uazapi.com'
UAZAPI_TOKEN = '9ef0cf61-87b3-444a-8769-07b0b74563e5'

try:
    # Verifica se ja existe
    cur.execute("SELECT id, nome FROM integracoes_api WHERE tenant_id = %s AND tipo = 'uazapi';", (TENANT_ID,))
    existing = cur.fetchone()
    if existing:
        print(f'IntegracaoAPI uazapi ja existe: id={existing[0]} nome={existing[1]!r}')
        integracao_id = existing[0]
    else:
        config = json.dumps({'token': UAZAPI_TOKEN})
        cur.execute("""INSERT INTO integracoes_api (
            tenant_id, nome, tipo, base_url, client_id, client_secret, username, password,
            grant_type, access_token, ativa, configuracoes_extras,
            data_criacao, data_atualizacao, api_token, api_key
        ) VALUES (%s, 'Uazapi TR Carrion', 'uazapi', %s, '', '', '', '',
                  '', '', TRUE, %s::jsonb, NOW(), NOW(), '', '')
        RETURNING id;""",
        (TENANT_ID, UAZAPI_URL, config))
        integracao_id = cur.fetchone()[0]
        print(f'IntegracaoAPI Uazapi criada: id={integracao_id}')

    # Linka CanalInbox -> integracao
    cur.execute("UPDATE inbox_canais SET integracao_id = %s WHERE id = %s AND tenant_id = %s;",
                (integracao_id, CANAL_ID, TENANT_ID))
    print(f'CanalInbox id={CANAL_ID} linkado a IntegracaoAPI id={integracao_id}')

    conn.commit()
    print('\nCOMMIT OK.\n')

    # Validar
    cur.execute("""SELECT c.id, c.nome, c.provedor, c.integracao_id, i.nome
                   FROM inbox_canais c LEFT JOIN integracoes_api i ON c.integracao_id = i.id
                   WHERE c.id = %s;""", (CANAL_ID,))
    r = cur.fetchone()
    print(f'Canal validado: id={r[0]} nome={r[1]!r} provedor={r[2]} integracao_id={r[3]} integracao_nome={r[4]!r}')

except Exception as e:
    conn.rollback()
    print(f'ERRO: {type(e).__name__}: {e}')
    raise
finally:
    cur.close(); conn.close()
