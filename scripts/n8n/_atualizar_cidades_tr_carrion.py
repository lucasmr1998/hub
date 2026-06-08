"""
PROD WRITE — Autorizado pelo usuario em 2026-05-18.
Substitui as 5 cidades ficticias do tenant tr-carrion (id=11) pelas 7 reais
extraidas de planos.md:
  Grupo A (FUXO 1): Agudos, Pederneiras, Pirajui, Piratininga
  Grupo B (FUXO 2): Americana, Bauru, Limeira
Todas em SP. Sem CEP especifico (toda a cidade conta).

Transacional: rollback automatico se algo falhar.
"""
import psycopg2
import psycopg2.extras
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')
conn = psycopg2.connect(
    host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
    database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10,
)
conn.autocommit = False
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

TENANT_ID = 11
CIDADES_NOVAS = [
    # (cidade, estado)
    ('Agudos',       'SP'),
    ('Pederneiras',  'SP'),
    ('Pirajui',      'SP'),
    ('Piratininga',  'SP'),
    ('Americana',    'SP'),
    ('Bauru',        'SP'),
    ('Limeira',      'SP'),
]

try:
    # Estado antes
    cur.execute("SELECT id, cidade, estado FROM viabilidade_cidadeviabilidade WHERE tenant_id = %s ORDER BY cidade;", (TENANT_ID,))
    antigas = cur.fetchall()
    print(f'Cidades atuais ({len(antigas)}):')
    for r in antigas:
        print(f'  id={r["id"]:3} {r["cidade"]}/{r["estado"]}')

    # Apaga as antigas
    cur.execute("DELETE FROM viabilidade_cidadeviabilidade WHERE tenant_id = %s;", (TENANT_ID,))
    print(f'\nDELETE: {cur.rowcount} cidades antigas removidas.')

    # Cria as novas (preciso ver as colunas obrigatorias antes)
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'viabilidade_cidadeviabilidade'
        ORDER BY ordinal_position;
    """)
    print('\nColunas da tabela:')
    for c in cur.fetchall():
        print(f'  {c[0]:25} {c[1]:25} nullable={c[2]:5} default={c[3]}')

    # INSERT novo
    print(f'\nInserindo {len(CIDADES_NOVAS)} novas cidades...')
    for cidade, estado in CIDADES_NOVAS:
        cur.execute("""
            INSERT INTO viabilidade_cidadeviabilidade
                (tenant_id, cidade, estado, cep, ativo, data_criacao, data_atualizacao)
            VALUES (%s, %s, %s, NULL, TRUE, NOW(), NOW())
            RETURNING id;
        """, (TENANT_ID, cidade, estado))
        new_id = cur.fetchone()['id']
        print(f'  id={new_id:3} {cidade}/{estado}')

    conn.commit()
    print('\nCOMMIT OK.\n')

    # Validacao
    cur.execute("SELECT id, cidade, estado, ativo FROM viabilidade_cidadeviabilidade WHERE tenant_id = %s ORDER BY cidade;", (TENANT_ID,))
    print('Estado final:')
    for r in cur.fetchall():
        print(f'  id={r["id"]:3} {r["cidade"]:15} / {r["estado"]}  ativo={r["ativo"]}')

except Exception as e:
    conn.rollback()
    print(f'\nERRO — rollback executado: {type(e).__name__}: {e}')
    raise

finally:
    cur.close()
    conn.close()
