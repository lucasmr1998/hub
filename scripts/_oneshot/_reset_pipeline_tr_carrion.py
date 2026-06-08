"""
Reformula pipeline tr-carrion SEM apagar dados:

1. Renomeia estagios existentes (IDs 52-56) pra novos nomes/slugs
2. Insere 2 novos estagios ("Aguardando Vendedor" e "Contrato Enviado")
3. Reordena tudo
4. Atualiza ConfiguracaoCRM pra apontar pro novo estagio inicial

Mapeamento (mantém IDs, oportunidades existentes seguem onde estão):
  52 Novo Lead       → Atendimento Ativo      (ordem 1, novo, #3b82f6)
  -- NOVO --         → Aguardando Vendedor   (ordem 2, qualif, #f59e0b)
  53 Em Contato      → Em Negociacao         (ordem 3, negoc, #8b5cf6)
  -- NOVO --         → Contrato Enviado      (ordem 4, negoc, #06b6d4)
  54 Proposta        → Aguardando Instalacao (ordem 5, fech,  #f97316)
  55 Cliente Ativo   → mantem                (ordem 6, cliente, #22c55e, ganho)
  56 Perdido         → mantem                (ordem 7, perdido, #ef4444, perda)
"""
import psycopg2
import psycopg2.extras
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')
TENANT_ID = 11

# UPDATE existentes (id, novo_nome, novo_slug, nova_ordem, novo_tipo, nova_cor, prob, sla)
ATUALIZACOES = [
    (52, 'Atendimento Ativo',      'atendimento-ativo',      1, 'novo',         '#3b82f6', 10,  2,    False, False),
    (53, 'Em Negociacao',          'em-negociacao',          3, 'negociacao',   '#8b5cf6', 50,  48,   False, False),
    (54, 'Aguardando Instalacao',  'aguardando-instalacao',  5, 'fechamento',   '#f97316', 90,  168,  False, False),
    (55, 'Cliente Ativo',          'cliente-ativo',          6, 'cliente',      '#22c55e', 100, None, True,  False),
    (56, 'Perdido',                'perdido',                7, 'perdido',      '#ef4444', 0,   None, False, True),
]

# INSERT novos (nome, slug, ordem, tipo, cor, prob, sla, is_g, is_p)
NOVOS = [
    ('Aguardando Vendedor', 'aguardando-vendedor', 2, 'qualificacao', '#f59e0b', 30, 4,   False, False),
    ('Contrato Enviado',    'contrato-enviado',    4, 'negociacao',   '#06b6d4', 70, 72,  False, False),
]

conn = psycopg2.connect(host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
                         database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
                         password=env['PROD_DB_PASSWORD'], connect_timeout=10)
conn.autocommit = False
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

try:
    # Estado antes
    cur.execute("""SELECT id, nome, slug, ordem FROM crm_pipeline_estagios
                   WHERE tenant_id = %s ORDER BY ordem;""", (TENANT_ID,))
    print('Estagios ANTES:')
    for r in cur.fetchall():
        print(f'  id={r["id"]:3} ordem={r["ordem"]} {r["nome"]!r:20} slug={r["slug"]}')

    # 1. UPDATE
    print('\n--- Atualizando estagios existentes ---')
    for eid, nome, slug, ordem, tipo, cor, prob, sla, is_g, is_p in ATUALIZACOES:
        cur.execute("""UPDATE crm_pipeline_estagios
            SET nome=%s, slug=%s, ordem=%s, tipo=%s, cor_hex=%s,
                probabilidade_padrao=%s, sla_horas=%s,
                is_final_ganho=%s, is_final_perdido=%s
            WHERE id=%s AND tenant_id=%s;""",
            (nome, slug, ordem, tipo, cor, prob, sla, is_g, is_p, eid, TENANT_ID))
        print(f'  id={eid} -> {nome!r} ordem={ordem}')

    # Pega pipeline_id (todos esses estagios estao no mesmo pipeline)
    cur.execute("SELECT DISTINCT pipeline_id FROM crm_pipeline_estagios WHERE tenant_id = %s;", (TENANT_ID,))
    pipeline_id = cur.fetchone()['pipeline_id']

    # 2. INSERT novos
    print('\n--- Inserindo novos estagios ---')
    novos_ids = []
    for nome, slug, ordem, tipo, cor, prob, sla, is_g, is_p in NOVOS:
        cur.execute("""INSERT INTO crm_pipeline_estagios
            (tenant_id, pipeline_id, nome, slug, ordem, cor_hex, icone_fa, tipo,
             is_final_ganho, is_final_perdido, probabilidade_padrao, sla_horas, ativo, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, 'fa-circle', %s, %s, %s, %s, %s, TRUE, NOW())
            RETURNING id;""",
            (TENANT_ID, pipeline_id, nome, slug, ordem, cor, tipo, is_g, is_p, prob, sla))
        new_id = cur.fetchone()['id']
        novos_ids.append((new_id, nome))
        print(f'  id={new_id} {nome!r} ordem={ordem}')

    # 3. Atualizar ConfiguracaoCRM (estagio inicial = id 52 que agora eh "Atendimento Ativo")
    cur.execute("""UPDATE crm_configuracao
        SET estagio_inicial_padrao_id = 52, pipeline_padrao_id = %s, data_atualizacao = NOW()
        WHERE tenant_id = %s;""", (pipeline_id, TENANT_ID))
    print(f'\nConfiguracaoCRM atualizada: estagio_inicial=52 pipeline={pipeline_id}')

    conn.commit()
    print('\nCOMMIT OK.\n')

    # Estado depois
    cur.execute("""SELECT id, nome, slug, ordem, tipo, is_final_ganho, is_final_perdido
                   FROM crm_pipeline_estagios WHERE tenant_id = %s ORDER BY ordem;""", (TENANT_ID,))
    print('Estagios DEPOIS:')
    for r in cur.fetchall():
        flag = ' (GANHO)' if r['is_final_ganho'] else (' (PERDIDO)' if r['is_final_perdido'] else '')
        print(f'  {r["ordem"]}. id={r["id"]:3} {r["nome"]!r:25} tipo={r["tipo"]:15}{flag}')

except Exception as e:
    conn.rollback()
    print(f'ERRO: {type(e).__name__}: {e}')
    raise
finally:
    cur.close(); conn.close()
