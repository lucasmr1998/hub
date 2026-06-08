"""Teste E2E em prod (transacao com ROLLBACK):

Pega um lead existente sem responsavel + cidade != Palhoca,
muda temporariamente cidade pra Palhoca, simula a logica do motor,
verifica atribuicao, ROLLBACK no fim. Nada persiste.
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

    # Acha uma oport ativa sem responsavel, com lead que tenha cidade
    cur.execute("""
        SELECT o.id, o.lead_id, l.cidade, l.nome_razaosocial
        FROM crm_oportunidades o
        JOIN leads_prospectos l ON l.id = o.lead_id
        WHERE o.tenant_id = 11 AND o.ativo = true
          AND o.responsavel_id IS NULL
          AND l.cidade IS NOT NULL AND l.cidade <> ''
        ORDER BY o.data_criacao DESC LIMIT 1;
    """)
    row = cur.fetchone()
    if not row:
        # Fallback: oport ativa qualquer com lead que tenha cidade
        cur.execute("""
            SELECT o.id, o.lead_id, l.cidade, l.nome_razaosocial
            FROM crm_oportunidades o
            JOIN leads_prospectos l ON l.id = o.lead_id
            WHERE o.tenant_id = 11 AND o.ativo = true
              AND l.cidade IS NOT NULL AND l.cidade <> ''
            ORDER BY o.data_criacao DESC LIMIT 1;
        """)
        row = cur.fetchone()
    oport_id, lead_id, cidade_orig, lead_nome = row
    print(f'Vou testar com oport={oport_id} lead="{lead_nome}" cidade_original={cidade_orig!r}')

    # Salva responsavel atual pra restaurar
    cur.execute("SELECT responsavel_id FROM crm_oportunidades WHERE id = %s;", (oport_id,))
    responsavel_orig = cur.fetchone()[0]
    print(f'responsavel_original={responsavel_orig}')

    # Limpa responsavel + muda cidade pra Palhoca
    cur.execute("UPDATE crm_oportunidades SET responsavel_id = NULL WHERE id = %s;", (oport_id,))
    cur.execute("UPDATE leads_prospectos SET cidade = 'Palhoça' WHERE id = %s;", (lead_id,))
    print('UPDATE aplicado: cidade=Palhoça, responsavel=NULL')

    # ==== SIMULA O MOTOR ====
    # Carrega contexto (cidade do lead)
    cur.execute("SELECT cidade FROM leads_prospectos WHERE id = %s;", (lead_id,))
    cidade_atual = cur.fetchone()[0]
    print(f'\nContexto montado: cidade={cidade_atual!r}')

    # Carrega regras de acao pura
    cur.execute("""
        SELECT id, nome, condicoes, acoes
        FROM crm_regras_pipeline_estagio
        WHERE tenant_id = 11 AND ativo = true AND estagio_id IS NULL
        ORDER BY prioridade;
    """)
    regras = cur.fetchall()
    print(f'Regras carregadas: {len(regras)}')

    # Avalia
    regra_match = None
    for rid, rnome, conds, acoes in regras:
        bate_tudo = bool(conds)
        for c in conds:
            tipo = c.get('tipo')
            campo = c.get('campo')
            valor_esperado = c.get('valor')
            operador = c.get('operador', 'igual')

            if tipo == 'lead_campo' and campo == 'cidade':
                valor_real = cidade_atual or ''
                if operador == 'igual':
                    bate = str(valor_real).strip() == str(valor_esperado).strip()
                else:
                    bate = False
                if not bate:
                    bate_tudo = False
                    break
            else:
                bate_tudo = False
                break
        if bate_tudo:
            regra_match = (rid, rnome, conds, acoes)
            print(f'  >>> Regra {rid} "{rnome}" BATEU')
            break

    assert regra_match is not None, 'ERRO: nenhuma regra bateu pra cidade=Palhoca'

    # Executa acao
    rid, rnome, conds, acoes = regra_match
    for acao in acoes:
        if acao.get('tipo') == 'atribuir_agente':
            user_id = acao.get('config', {}).get('user_id')
            print(f'\nExecutando acao atribuir_agente user_id={user_id}')
            cur.execute("""
                UPDATE crm_oportunidades SET responsavel_id = %s
                WHERE id = %s AND responsavel_id IS NULL;
            """, (user_id, oport_id))
            print(f'  rows atualizadas: {cur.rowcount}')

    # Verifica resultado
    cur.execute("""
        SELECT o.responsavel_id, u.username, u.first_name, u.last_name
        FROM crm_oportunidades o
        LEFT JOIN auth_user u ON u.id = o.responsavel_id
        WHERE o.id = %s;
    """, (oport_id,))
    rid_final, uname, fname, lname = cur.fetchone()
    print(f'\nResultado:')
    print(f'  oport.responsavel_id = {rid_final}')
    print(f'  user = {uname} ({fname} {lname})')

    assert rid_final == 23, f'FALHOU: responsavel={rid_final}, esperado 23'
    assert uname == 'flavia.vidoto', f'FALHOU: user={uname}'

    print('\n========== TESTE PASSOU — atribuiria Flavia corretamente ==========')

finally:
    conn.rollback()
    print('\nROLLBACK — nada persistido em prod.')
    cur.close()
    conn.close()
