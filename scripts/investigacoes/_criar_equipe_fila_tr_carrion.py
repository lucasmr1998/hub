"""
Cria EquipeInbox + FilaInbox pra tr-carrion + adiciona lucas.carrion como membro.

Idempotente.
"""
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.prod_readonly')
TENANT_ID = 11

conn = psycopg2.connect(host=env['PROD_DB_HOST'], port=int(env['PROD_DB_PORT']),
                         database=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
                         password=env['PROD_DB_PASSWORD'], connect_timeout=10)
conn.autocommit = False
cur = conn.cursor()

try:
    # 1. Equipe (id_padrao do tenant)
    cur.execute("SELECT id FROM inbox_equipes WHERE tenant_id=%s AND nome='Vendedores Vero';", (TENANT_ID,))
    eq = cur.fetchone()
    if eq:
        equipe_id = eq[0]; print(f'Equipe ja existe: id={equipe_id}')
    else:
        # Estrutura provavel: tenant_id, nome, descricao, ativo, criado_em
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='inbox_equipes' ORDER BY ordinal_position;")
        cols = [r[0] for r in cur.fetchall()]
        print(f'Colunas equipes: {cols}')
        cur.execute("""INSERT INTO inbox_equipes (tenant_id, nome, descricao, cor_hex, ativo, criado_em)
                       VALUES (%s, 'Vendedores Vero', 'Equipe de vendas Vero TR Carrion', '#3b82f6', TRUE, NOW())
                       RETURNING id;""", (TENANT_ID,))
        equipe_id = cur.fetchone()[0]
        print(f'Equipe criada: id={equipe_id}')

    # 2. Fila
    cur.execute("SELECT id FROM inbox_filas WHERE tenant_id=%s AND nome='Atendimento Vero';", (TENANT_ID,))
    fl = cur.fetchone()
    if fl:
        fila_id = fl[0]; print(f'Fila ja existe: id={fila_id}')
    else:
        cur.execute("""INSERT INTO inbox_filas
            (tenant_id, equipe_id, nome, descricao, prioridade, modo_distribuicao, ativo, criado_em, mensagem_fora_horario)
            VALUES (%s, %s, 'Atendimento Vero', 'Fila principal de atendimento', 10, 'round_robin', TRUE, NOW(), '')
            RETURNING id;""", (TENANT_ID, equipe_id))
        fila_id = cur.fetchone()[0]
        print(f'Fila criada: id={fila_id}')

    # 3. Adiciona lucas.carrion como membro
    cur.execute("SELECT id FROM auth_user WHERE username='lucas.carrion';")
    user_row = cur.fetchone()
    if not user_row:
        print('User lucas.carrion nao encontrado!')
        conn.rollback(); raise SystemExit(1)
    user_id = user_row[0]

    cur.execute("SELECT id FROM inbox_membros_equipe WHERE tenant_id=%s AND equipe_id=%s AND user_id=%s;",
                (TENANT_ID, equipe_id, user_id))
    if cur.fetchone():
        print(f'lucas.carrion (id={user_id}) ja eh membro')
    else:
        # Verificar colunas
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='inbox_membros_equipe' ORDER BY ordinal_position;")
        cols = [r[0] for r in cur.fetchall()]
        print(f'Colunas membros_equipe: {cols}')
        # Tentar insert
        try:
            cur.execute("""INSERT INTO inbox_membros_equipe
                (tenant_id, equipe_id, user_id, cargo, adicionado_em)
                VALUES (%s, %s, %s, 'agente', NOW());""",
                (TENANT_ID, equipe_id, user_id))
            print(f'lucas.carrion (id={user_id}) adicionado como membro')
        except Exception as e:
            conn.rollback()
            print(f'Falha insert membro: {e}')
            raise

    conn.commit()
    print('\nCOMMIT OK.')
    print(f'\nUse FilaInbox id={fila_id} pra distribuir conversas.')

except Exception as e:
    conn.rollback()
    print(f'ERRO: {type(e).__name__}: {e}')
    raise
finally:
    cur.close(); conn.close()
