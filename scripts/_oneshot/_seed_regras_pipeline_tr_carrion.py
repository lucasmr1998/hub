"""
Seed das regras de automacao de pipeline pra tr-carrion.

Cria 4 regras iniciais:
  1. Atendimento Ativo -> Aguardando Vendedor (quando bot concluiu)
  2. Atendimento Ativo -> Aguardando Vendedor (quando cliente pediu humano)
  3. Aguardando Vendedor -> Em Negociacao (quando vendedor atribuiu)
  4. Atendimento Ativo -> Aguardando Vendedor (lead completo)

Idempotente: aborta se ja existem regras pro tenant.
"""
import json
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')
TENANT_ID = 11

# Estagio IDs reais do tr-carrion (do reset anterior)
ESTAGIO_AGUARDANDO_VENDEDOR = 64
ESTAGIO_EM_NEGOCIACAO = 53

REGRAS = [
    {
        'estagio_id': ESTAGIO_AGUARDANDO_VENDEDOR,
        'nome': 'Bot concluiu conversa',
        'prioridade': 10,
        'condicoes': [
            {'tipo': 'oportunidade_dados_custom', 'campo': 'atendimento_estado',
             'operador': 'igual', 'valor': 'concluido'}
        ],
    },
    {
        'estagio_id': ESTAGIO_AGUARDANDO_VENDEDOR,
        'nome': 'Cliente pediu atendimento humano',
        'prioridade': 20,
        'condicoes': [
            {'tipo': 'conversa_modo', 'campo': '', 'operador': 'igual', 'valor': 'humano'}
        ],
    },
    {
        'estagio_id': ESTAGIO_AGUARDANDO_VENDEDOR,
        'nome': 'Bot finalizado',
        'prioridade': 30,
        'condicoes': [
            {'tipo': 'conversa_modo', 'campo': '', 'operador': 'igual', 'valor': 'finalizado_bot'}
        ],
    },
    {
        'estagio_id': ESTAGIO_EM_NEGOCIACAO,
        'nome': 'Vendedor assumiu conversa',
        'prioridade': 10,
        'condicoes': [
            {'tipo': 'conversa_atribuida', 'campo': '', 'operador': 'existe', 'valor': ''}
        ],
    },
]

conn = psycopg2.connect(host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
                         database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
                         password=env['PROD_DB_PASSWORD'], connect_timeout=10)
conn.autocommit = False
cur = conn.cursor()

try:
    cur.execute("SELECT COUNT(*) FROM crm_regras_pipeline_estagio WHERE tenant_id = %s;", (TENANT_ID,))
    n = cur.fetchone()[0]
    if n > 0:
        print(f'Tenant ja tem {n} regras. Abortando (idempotencia).')
        conn.rollback()
        raise SystemExit(0)

    for r in REGRAS:
        cur.execute("""INSERT INTO crm_regras_pipeline_estagio
            (tenant_id, estagio_id, nome, condicoes, ativo, prioridade,
             total_disparos, criado_em, atualizado_em)
            VALUES (%s, %s, %s, %s::jsonb, TRUE, %s, 0, NOW(), NOW())
            RETURNING id;""",
            (TENANT_ID, r['estagio_id'], r['nome'], json.dumps(r['condicoes']), r['prioridade']))
        rid = cur.fetchone()[0]
        print(f'  Regra id={rid} estagio={r["estagio_id"]} prioridade={r["prioridade"]} — {r["nome"]!r}')

    conn.commit()
    print('\nCOMMIT OK.')

    cur.execute("""SELECT r.id, e.nome AS estagio, r.nome AS regra, r.condicoes
                   FROM crm_regras_pipeline_estagio r
                   JOIN crm_pipeline_estagios e ON r.estagio_id = e.id
                   WHERE r.tenant_id = %s ORDER BY e.ordem, r.prioridade;""", (TENANT_ID,))
    print('\nRegras criadas:')
    for row in cur.fetchall():
        print(f'  id={row[0]} ESTAGIO={row[1]} REGRA={row[2]!r}')

except Exception as e:
    conn.rollback()
    print(f'ERRO: {type(e).__name__}: {e}')
    raise
finally:
    cur.close(); conn.close()
