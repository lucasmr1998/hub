"""
PROVISIONAMENTO EM PRODUCAO: cria Pipeline + Estagios + ConfiguracaoCRM
pro tenant tr-carrion (id=11).

Autorizado pelo usuario em 2026-05-18.

Idempotente: nao recria se ja existir pipeline.
Faz tudo numa transacao — rollback automatico se algo falhar.
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
TENANT_SLUG = 'tr-carrion'

PIPELINE = {
    'nome': 'Vendas Internet',
    'slug': 'vendas-internet',
    'tipo': 'vendas',
    'cor_hex': '#252020',
    'icone_fa': 'fa-funnel-dollar',
    'padrao': True,
    'ativo': True,
    'ordem': 0,
}

ESTAGIOS = [
    # (ordem, nome, slug, tipo, cor, prob, sla_h, is_ganho, is_perdido)
    (1, 'Novo Lead',       'novo-lead',       'novo',         '#94a3b8', 10,  None, False, False),
    (2, 'Em Contato',      'em-contato',      'qualificacao', '#3b82f6', 30,  48,   False, False),
    (3, 'Proposta',        'proposta',        'negociacao',   '#f59e0b', 60,  72,   False, False),
    (4, 'Cliente Ativo',   'cliente-ativo',   'cliente',      '#22c55e', 100, None, True,  False),
    (5, 'Perdido',         'perdido',         'perdido',      '#ef4444', 0,   None, False, True),
]

try:
    # Sanity: confere que tr-carrion existe e nao tem pipeline ja
    cur.execute("SELECT id, slug, nome FROM sistema_tenant WHERE id = %s AND slug = %s;", (TENANT_ID, TENANT_SLUG))
    t = cur.fetchone()
    if not t:
        raise SystemExit(f'Tenant id={TENANT_ID} slug={TENANT_SLUG!r} nao existe!')
    print(f'Tenant: id={t["id"]} slug={t["slug"]!r} nome={t["nome"]!r}')

    cur.execute("SELECT COUNT(*) AS n FROM crm_pipelines WHERE tenant_id = %s;", (TENANT_ID,))
    n = cur.fetchone()['n']
    if n > 0:
        print(f'Ja existem {n} pipelines pro tenant. Abortando (idempotencia).')
        conn.rollback()
        raise SystemExit(0)

    # 1. Cria Pipeline
    print('\nCriando Pipeline...')
    cur.execute("""
        INSERT INTO crm_pipelines (tenant_id, nome, slug, tipo, cor_hex, icone_fa, padrao, ativo, ordem, criado_em, descricao)
        VALUES (%(tenant_id)s, %(nome)s, %(slug)s, %(tipo)s, %(cor_hex)s, %(icone_fa)s, %(padrao)s, %(ativo)s, %(ordem)s, NOW(), '')
        RETURNING id;
    """, {**PIPELINE, 'tenant_id': TENANT_ID})
    pipeline_id = cur.fetchone()['id']
    print(f'  Pipeline id={pipeline_id} criado: {PIPELINE["nome"]!r}')

    # 2. Cria Estagios
    print('\nCriando Estagios...')
    estagio_ids = {}
    for ordem, nome, slug, tipo, cor, prob, sla_h, is_ganho, is_perdido in ESTAGIOS:
        cur.execute("""
            INSERT INTO crm_pipeline_estagios
                (tenant_id, pipeline_id, nome, slug, ordem, cor_hex, icone_fa, tipo,
                 is_final_ganho, is_final_perdido, probabilidade_padrao, sla_horas, ativo, criado_em)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
            RETURNING id;
        """, (TENANT_ID, pipeline_id, nome, slug, ordem, cor, 'fa-circle', tipo,
              is_ganho, is_perdido, prob, sla_h))
        eid = cur.fetchone()['id']
        estagio_ids[slug] = eid
        print(f'  Estagio id={eid:4} ordem={ordem} {nome!r:20} ({tipo})')

    estagio_inicial = estagio_ids['novo-lead']

    # 3. Cria/atualiza ConfiguracaoCRM
    print('\nConfigurando ConfiguracaoCRM...')
    cur.execute("SELECT id FROM crm_configuracao WHERE tenant_id = %s;", (TENANT_ID,))
    cfg = cur.fetchone()
    if cfg:
        cur.execute("""
            UPDATE crm_configuracao
            SET pipeline_padrao_id = %s,
                estagio_inicial_padrao_id = %s,
                criar_oportunidade_automatico = TRUE
            WHERE id = %s;
        """, (pipeline_id, estagio_inicial, cfg['id']))
        print(f'  ConfiguracaoCRM id={cfg["id"]} atualizada')
    else:
        cur.execute("""
            INSERT INTO crm_configuracao
                (tenant_id, sla_alerta_horas_padrao, criar_oportunidade_automatico,
                 score_minimo_auto_criacao, pipeline_padrao_id, estagio_inicial_padrao_id,
                 notificar_responsavel_nova_oportunidade, notificar_sla_breach,
                 distribuicao_modo, preview_regras_max, data_atualizacao)
            VALUES (%s, 48, TRUE, 7, %s, %s, TRUE, TRUE, 'desativado', 50, NOW())
            RETURNING id;
        """, (TENANT_ID, pipeline_id, estagio_inicial))
        cfg_id = cur.fetchone()['id']
        print(f'  ConfiguracaoCRM id={cfg_id} criada')

    conn.commit()
    print('\nCommit OK.\n')

    # Validacao final
    cur.execute("SELECT id, nome, padrao FROM crm_pipelines WHERE tenant_id = %s;", (TENANT_ID,))
    print('Pipelines do tenant:')
    for p in cur.fetchall():
        print(f'  {dict(p)}')

    cur.execute("""SELECT id, nome, ordem, tipo, is_final_ganho, is_final_perdido
                   FROM crm_pipeline_estagios WHERE tenant_id = %s ORDER BY ordem;""", (TENANT_ID,))
    print('\nEstagios:')
    for e in cur.fetchall():
        print(f'  {dict(e)}')

    cur.execute("""SELECT id, pipeline_padrao_id, estagio_inicial_padrao_id, criar_oportunidade_automatico
                   FROM crm_configuracao WHERE tenant_id = %s;""", (TENANT_ID,))
    print('\nConfiguracaoCRM:')
    for c in cur.fetchall():
        print(f'  {dict(c)}')

except Exception as e:
    conn.rollback()
    print(f'\nERRO — rollback executado: {type(e).__name__}: {e}')
    raise

finally:
    cur.close()
    conn.close()
