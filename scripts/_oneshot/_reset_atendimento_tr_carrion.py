"""
RESET TOTAL do atendimento do tr-carrion (tenant id=11).

Versao dinamica: descobre o nome da FK em cada tabela referenciada
em runtime e gera os DELETEs correspondentes. Tudo em uma transacao.
"""
import psycopg2
import sys
import io
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TENANT_ID = 11
env = dotenv_values('.env.prod_readonly')
TELEFONES_TENANT = []


def hub_conn():
    return psycopg2.connect(
        host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
        database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
        password=env['PROD_DB_PASSWORD'], connect_timeout=10,
    )


def n8n_conn():
    return psycopg2.connect(
        host='103.199.187.4', port=5434, database='banco_n8n',
        user='admin', password='Gremio271293@', connect_timeout=10,
    )


def fk_col(cur, child_table, parent_table):
    """Descobre o nome da coluna FK em child_table que referencia parent_table."""
    cur.execute("""
        SELECT kcu.column_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu ON kcu.constraint_name=tc.constraint_name
          JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name=tc.constraint_name
         WHERE tc.constraint_type='FOREIGN KEY'
           AND tc.table_name=%s AND ccu.table_name=%s
         LIMIT 1;
    """, (child_table, parent_table))
    r = cur.fetchone()
    return r[0] if r else None


def step(cur, label, sql, params=None):
    cur.execute(sql, params or ())
    print(f'  {label}: {cur.rowcount} linhas')


def delete_refs(cur, parent_table, parent_subquery, refs, params):
    """Pra cada child_table em refs, descobre a FK e roda DELETE."""
    for child in refs:
        col = fk_col(cur, child, parent_table)
        if not col:
            print(f'  {child}: <sem FK detectada, pulado>')
            continue
        sql = f"DELETE FROM {child} WHERE {col} IN ({parent_subquery});"
        step(cur, f'{child} ({col})', sql, params)


# ========== HUB (tenant tr-carrion) ==========
print('--- HUB tenant=11 ---')
conn = hub_conn()
conn.autocommit = False
cur = conn.cursor()
try:
    # 0. Coleta telefones do tenant pra usar como filtro depois no N8N
    cur.execute("SELECT DISTINCT telefone FROM leads_prospectos WHERE tenant_id=%s AND telefone IS NOT NULL;", (TENANT_ID,))
    norm = set()
    for r in cur.fetchall():
        t = r[0]
        d = ''.join(c for c in t if c.isdigit())
        if d:
            norm.add(d); norm.add(t)
    TELEFONES_TENANT = list(norm)
    print(f'  Telefones do tenant: {len(TELEFONES_TENANT)}')

    conv_sub = "SELECT id FROM inbox_conversas WHERE tenant_id=%s"
    op_sub   = "SELECT id FROM crm_oportunidades WHERE tenant_id=%s"
    lead_sub = "SELECT id FROM leads_prospectos WHERE tenant_id=%s"

    # 1. Dependentes de inbox_conversas
    REFS_CONV = [
        'inbox_mensagens', 'inbox_notas_internas',
        'inbox_avaliacao_atendimento', 'inbox_historico_transferencia',
        'inbox_conversas_etiquetas', 'suporte_perguntas_sem_resposta',
    ]
    delete_refs(cur, 'inbox_conversas', conv_sub, REFS_CONV, (TENANT_ID,))
    step(cur, 'inbox_conversas', "DELETE FROM inbox_conversas WHERE tenant_id=%s;", (TENANT_ID,))

    # 2. Dependentes de crm_oportunidades + outros CRM com tenant_id
    step(cur, 'crm_notas_internas_mencoes',
         "DELETE FROM crm_notas_internas_mencoes WHERE notainterna_id IN (SELECT id FROM crm_notas_internas WHERE tenant_id=%s);", (TENANT_ID,))
    step(cur, 'crm_notas_internas', "DELETE FROM crm_notas_internas WHERE tenant_id=%s;", (TENANT_ID,))
    # crm_historico_estagio referencia op — deletar via op_sub pra pegar todos
    REFS_OP = ['crm_itens_oportunidade', 'crm_oportunidades_tags',
               'crm_historico_estagio', 'crm_tarefas', 'crm_alertas_retencao']
    delete_refs(cur, 'crm_oportunidades', op_sub, REFS_OP, (TENANT_ID,))
    step(cur, 'crm_oportunidades', "DELETE FROM crm_oportunidades WHERE tenant_id=%s;", (TENANT_ID,))

    # 3. Dependentes de leads_prospectos (todas as FKs descobertas dinamicamente)
    REFS_LEAD = [
        'atendimento_log_fluxo', 'atendimentos_fluxo',
        'automacoes_controleexecucao', 'automacoes_execucaopendente', 'automacoes_logexecucao',
        'cadastros_clientes', 'clientes_hubsoft', 'clientes_sgp',
        'crm_membros_segmento', 'deteccao_campanha', 'documentos_lead',
        'historico_contato', 'imagens_lead_prospecto',
        'integracoes_cliente_consolidado', 'logs_integracao',
        'marketing_envio_email', 'prospectos',
    ]
    delete_refs(cur, 'leads_prospectos', lead_sub, REFS_LEAD, (TENANT_ID,))

    # 4. Notificacoes do tenant
    step(cur, 'notificacoes (tenant)', "DELETE FROM notificacoes_notificacao WHERE tenant_id=%s;", (TENANT_ID,))

    # 5. Leads
    step(cur, 'leads_prospectos', "DELETE FROM leads_prospectos WHERE tenant_id=%s;", (TENANT_ID,))

    conn.commit()
    print('\nHUB: COMMIT OK')
except Exception as e:
    conn.rollback()
    print(f'\nHUB: ROLLBACK — {type(e).__name__}: {e}')
    raise
finally:
    cur.close(); conn.close()


# ========== N8N (vero_session + buffer) ==========
print('\n--- N8N banco_n8n (escopo: telefones tr-carrion) ---')
if not TELEFONES_TENANT:
    print('  Nenhum telefone do tenant coletado — pulando N8N')
else:
    conn2 = n8n_conn()
    conn2.autocommit = False
    cur2 = conn2.cursor()
    try:
        step(cur2, 'vero_session',
             "DELETE FROM vero_session WHERE telefone = ANY(%s);", (TELEFONES_TENANT,))
        step(cur2, 'vero_message_buffer',
             "DELETE FROM vero_message_buffer WHERE telefone = ANY(%s);", (TELEFONES_TENANT,))
        conn2.commit()
        print('\nN8N: COMMIT OK')
    except Exception as e:
        conn2.rollback()
        print(f'\nN8N: ROLLBACK — {type(e).__name__}: {e}')
        raise
    finally:
        cur2.close(); conn2.close()

print('\n=== RESET CONCLUIDO ===')
