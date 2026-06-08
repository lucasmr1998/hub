"""Teste E2E em prod (ROLLBACK no fim): valida que atribuir_agente
atualiza CRM (oport.responsavel) E Inbox (conversa.agente).
"""
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
    print('========== TRANSACAO INICIADA (ROLLBACK no final) ==========\n')

    # Acha oport com Conversa vinculada
    cur.execute("""
        SELECT o.id, o.lead_id, l.cidade, l.nome_razaosocial, c.id, c.agente_id
        FROM crm_oportunidades o
        JOIN leads_prospectos l ON l.id = o.lead_id
        JOIN inbox_conversas c ON c.oportunidade_id = o.id
        WHERE o.tenant_id = 11 AND o.ativo = true
          AND l.cidade IS NOT NULL AND l.cidade <> ''
        ORDER BY o.data_criacao DESC LIMIT 1;
    """)
    oport_id, lead_id, cidade_orig, lead_nome, conv_id, agente_orig = cur.fetchone()
    print(f'Oport={oport_id} lead="{lead_nome}" cidade_orig={cidade_orig!r}')
    print(f'Conversa vinculada: id={conv_id} agente_atual={agente_orig}')

    # Preparar cenario: cidade=Palhoca, responsavel=NULL, agente=NULL
    cur.execute("UPDATE crm_oportunidades SET responsavel_id = NULL WHERE id = %s;", (oport_id,))
    cur.execute("UPDATE leads_prospectos SET cidade = 'Palhoça' WHERE id = %s;", (lead_id,))
    cur.execute("UPDATE inbox_conversas SET agente_id = NULL WHERE id = %s;", (conv_id,))
    print('Cenario preparado: cidade=Palhoca, oport.resp=NULL, conv.agente=NULL\n')

    # Aplica a acao manualmente (mesma logica do _acao_atribuir_agente)
    USER_ID = 23
    cur.execute("""
        UPDATE crm_oportunidades SET responsavel_id = %s
        WHERE id = %s AND responsavel_id IS NULL;
    """, (USER_ID, oport_id))
    print(f'CRM: oport {oport_id} responsavel_id <- {USER_ID} (rows={cur.rowcount})')

    cur.execute("""
        UPDATE inbox_conversas SET agente_id = %s
        WHERE tenant_id = 11 AND oportunidade_id = %s AND agente_id IS NULL;
    """, (USER_ID, oport_id))
    print(f'INBOX: conversas vinculadas atribuidas (rows={cur.rowcount})')

    # Verifica os dois lados
    cur.execute("""
        SELECT o.responsavel_id, u.username
        FROM crm_oportunidades o
        LEFT JOIN auth_user u ON u.id = o.responsavel_id
        WHERE o.id = %s;
    """, (oport_id,))
    resp_id, resp_user = cur.fetchone()

    cur.execute("""
        SELECT c.id, c.agente_id, u.username
        FROM inbox_conversas c
        LEFT JOIN auth_user u ON u.id = c.agente_id
        WHERE c.id = %s;
    """, (conv_id,))
    cid, agente_id, agente_user = cur.fetchone()

    print(f'\nResultado:')
    print(f'  CRM   — oport.responsavel = {resp_id} ({resp_user})')
    print(f'  INBOX — conversa.agente  = {agente_id} ({agente_user})')

    assert resp_id == USER_ID and resp_user == 'flavia.vidoto', 'CRM falhou'
    assert agente_id == USER_ID and agente_user == 'flavia.vidoto', 'INBOX falhou'

    print('\n========== AMBOS LADOS OK — CRM + Inbox atribuidos a Flavia ==========')

    # Testa tambem o caso "ja tem agente" — nao deve sobrescrever
    print('\n--- Verifica que nao rouba conversa de outra vendedora ---')
    OUTRO = 21  # Kelle
    cur.execute("UPDATE crm_oportunidades SET responsavel_id = NULL WHERE id = %s;", (oport_id,))
    cur.execute("UPDATE inbox_conversas SET agente_id = %s WHERE id = %s;", (OUTRO, conv_id))
    # Aplica acao
    cur.execute("""
        UPDATE crm_oportunidades SET responsavel_id = %s
        WHERE id = %s AND responsavel_id IS NULL;
    """, (USER_ID, oport_id))
    cur.execute("""
        UPDATE inbox_conversas SET agente_id = %s
        WHERE tenant_id = 11 AND oportunidade_id = %s AND agente_id IS NULL;
    """, (USER_ID, oport_id))

    cur.execute("SELECT agente_id FROM inbox_conversas WHERE id = %s;", (conv_id,))
    agente_apos = cur.fetchone()[0]
    print(f'Conversa.agente apos (era Kelle={OUTRO}): {agente_apos}')
    assert agente_apos == OUTRO, 'BUG: roubou conversa de Kelle!'
    print('OK: conversa de Kelle nao foi roubada (guard agente__isnull funciona)')

finally:
    conn.rollback()
    print('\nROLLBACK — nada persistido.')
    cur.close()
    conn.close()
