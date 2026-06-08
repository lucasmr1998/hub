"""Teste E2E (transacao com ROLLBACK):

Valida que a regra so dispara quando bot ja terminou:
- cenario 1: conversa.modo='bot' -> regra NAO dispara
- cenario 2: conversa.modo='finalizado_bot' -> regra dispara
- cenario 3: conversa.modo='humano' -> regra dispara
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


def avaliar_regra_palhoca(cur, oport_id, lead_id, conv_id):
    """Simula a logica do motor: carrega condicoes da regra 16 e avalia."""
    cur.execute("SELECT condicoes FROM crm_regras_pipeline_estagio WHERE id = 16;")
    conds = cur.fetchone()[0]

    # Coleta contexto
    cur.execute("SELECT cidade FROM leads_prospectos WHERE id = %s;", (lead_id,))
    cidade = cur.fetchone()[0]
    cur.execute("""
        SELECT array_agg(modo_atendimento)
        FROM inbox_conversas
        WHERE tenant_id = 11 AND oportunidade_id = %s;
    """, (oport_id,))
    modos = set(cur.fetchone()[0] or [])

    # Avalia cada condicao (AND)
    bate_tudo = True
    for c in conds:
        tipo = c.get('tipo')
        operador = c.get('operador', 'igual')
        valor = c.get('valor')
        if tipo == 'lead_campo' and c.get('campo') == 'cidade':
            bate = str(cidade or '').strip() == str(valor).strip() if operador == 'igual' else False
        elif tipo == 'conversa_modo':
            if operador == 'igual':
                bate = valor in modos
            elif operador == 'diferente':
                bate = valor not in modos
            else:
                bate = False
        else:
            bate = False
        if not bate:
            bate_tudo = False
            break
    return bate_tudo, cidade, modos


try:
    print('========== TRANSACAO (ROLLBACK no final) ==========\n')

    # Pega oport + lead + conversa pra testar
    cur.execute("""
        SELECT o.id, o.lead_id, c.id
        FROM crm_oportunidades o
        JOIN inbox_conversas c ON c.oportunidade_id = o.id
        WHERE o.tenant_id = 11 AND o.ativo = true
        ORDER BY o.data_criacao DESC LIMIT 1;
    """)
    oport_id, lead_id, conv_id = cur.fetchone()
    print(f'Testando: oport={oport_id} lead={lead_id} conv={conv_id}\n')

    # Setup base: cidade=Palhoca, sem responsavel, sem agente
    cur.execute("UPDATE crm_oportunidades SET responsavel_id = NULL WHERE id = %s;", (oport_id,))
    cur.execute("UPDATE leads_prospectos SET cidade = 'Palhoça' WHERE id = %s;", (lead_id,))
    cur.execute("UPDATE inbox_conversas SET agente_id = NULL WHERE id = %s;", (conv_id,))

    for modo_teste in ['bot', 'finalizado_bot', 'humano']:
        cur.execute("UPDATE inbox_conversas SET modo_atendimento = %s WHERE id = %s;", (modo_teste, conv_id))
        bate, cidade, modos = avaliar_regra_palhoca(cur, oport_id, lead_id, conv_id)
        esperado = (modo_teste != 'bot')
        ok = 'OK' if bate == esperado else 'ERRO'
        print(f'  modo="{modo_teste:15s}" modos={modos} -> regra_bate={bate} (esperado={esperado}) {ok}')
        assert bate == esperado, f'FALHOU em modo={modo_teste}'

    print('\n========== TODOS OS CENARIOS PASSARAM ==========')

finally:
    conn.rollback()
    print('\nROLLBACK.')
    cur.close()
    conn.close()
