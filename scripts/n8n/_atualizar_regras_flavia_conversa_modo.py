"""Atualiza as 3 regras de roteamento Flavia (IDs 16/17/18) adicionando
condicao extra: conversa_modo != bot. Assim a regra so dispara depois
que o bot terminou (modo vira finalizado_bot ou humano).
"""
import json
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
conn.autocommit = False
cur = conn.cursor()

try:
    REGRAS = [
        (16, 'Palhoça'),
        (17, 'Novo Hamburgo'),
        (18, 'Francisco Beltrão'),
    ]

    print('Antes do UPDATE:')
    cur.execute("SELECT id, nome, condicoes FROM crm_regras_pipeline_estagio WHERE id IN (16,17,18) ORDER BY id;")
    for r in cur.fetchall():
        print(f'  id={r[0]} condicoes={r[2]}')

    for rid, cidade in REGRAS:
        novas_condicoes = [
            {'tipo': 'lead_campo', 'campo': 'cidade', 'operador': 'igual', 'valor': cidade},
            {'tipo': 'conversa_modo', 'operador': 'diferente', 'valor': 'bot'},
        ]
        cur.execute("""
            UPDATE crm_regras_pipeline_estagio
            SET condicoes = %s::jsonb, atualizado_em = NOW()
            WHERE id = %s;
        """, (json.dumps(novas_condicoes), rid))
        print(f'\nUPDATE regra {rid} (cidade={cidade}) — rows={cur.rowcount}')

    print('\nDepois do UPDATE:')
    cur.execute("SELECT id, nome, condicoes FROM crm_regras_pipeline_estagio WHERE id IN (16,17,18) ORDER BY id;")
    for r in cur.fetchall():
        print(f'  id={r[0]} condicoes={r[2]}')

    conn.commit()
    print('\nCOMMIT.')
finally:
    cur.close()
    conn.close()
