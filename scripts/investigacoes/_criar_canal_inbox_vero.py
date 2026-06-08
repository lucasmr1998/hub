"""
Cria CanalInbox "Vero WhatsApp" pro tenant tr-carrion (id=11).
Idempotente: aborta se ja existe canal whatsapp pro tenant.
"""
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')
conn = psycopg2.connect(host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
                         database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
                         password=env['PROD_DB_PASSWORD'], connect_timeout=10)
conn.autocommit = False
cur = conn.cursor()

TENANT_ID = 11
NUMERO_BOT = '553181167572'

try:
    # Checa se ja existe
    cur.execute("""SELECT id, nome FROM inbox_canais
                   WHERE tenant_id = %s AND tipo = 'whatsapp' AND identificador_canal = %s;""",
                (TENANT_ID, NUMERO_BOT))
    existing = cur.fetchone()
    if existing:
        print(f'Canal ja existe: id={existing[0]} nome={existing[1]!r}')
        conn.rollback()
        raise SystemExit(0)

    cur.execute("""INSERT INTO inbox_canais
        (tenant_id, tipo, nome, ativo, configuracao, criado_em,
         identificador_canal, provedor)
        VALUES (%s, 'whatsapp', 'Vero WhatsApp', TRUE,
                '{"webhook_n8n":"https://automation-n8n.v4riem.easypanel.host/webhook/vero-orquestrador"}'::jsonb,
                NOW(), %s, 'uazapi')
        RETURNING id;""",
        (TENANT_ID, NUMERO_BOT))
    canal_id = cur.fetchone()[0]
    print(f'Canal criado: id={canal_id} "Vero WhatsApp" tipo=whatsapp provedor=uazapi numero={NUMERO_BOT}')

    conn.commit()
    print('\nCOMMIT OK.\n')

    # Validar
    cur.execute("""SELECT id, tipo, nome, identificador_canal, provedor, ativo
                   FROM inbox_canais WHERE tenant_id = %s;""", (TENANT_ID,))
    print('Canais do tenant tr-carrion:')
    for r in cur.fetchall():
        print(f'  id={r[0]:3} tipo={r[1]:10} nome={r[2]!r:20} numero={r[3]:15} provedor={r[4]:10} ativo={r[5]}')

except Exception as e:
    conn.rollback()
    print(f'ERRO: {type(e).__name__}: {e}')
    raise
finally:
    cur.close()
    conn.close()
