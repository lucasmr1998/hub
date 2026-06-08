"""
Cria tabela vero_session no banco_n8n (Postgres dedicado pro fluxo Vero do TR Carrion).

Conecta via porta publica do EasyPanel (5434, mesmo padrao do hubbanco em 5433).
"""
import psycopg2

CONN = dict(
    host='103.199.187.4',
    port=5434,
    database='banco_n8n',
    user='admin',
    password='Gremio271293@',
    connect_timeout=10,
)

SQL = """
CREATE TABLE IF NOT EXISTS vero_session (
    telefone        VARCHAR(20) PRIMARY KEY,
    nodo_atual      VARCHAR(40) NOT NULL DEFAULT 'inicio',
    dados           JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em       TIMESTAMP NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vero_session_atualizado ON vero_session (atualizado_em DESC);
"""

def main():
    print(f"Conectando em {CONN['host']}:{CONN['port']}/{CONN['database']}...")
    conn = psycopg2.connect(**CONN)
    conn.autocommit = True
    cur = conn.cursor()
    print('Conectou. Versao do server:')
    cur.execute('SELECT version();')
    print(' ', cur.fetchone()[0])

    print('\nCriando tabela vero_session...')
    cur.execute(SQL)
    print('  OK.')

    print('\nValidando estrutura da tabela:')
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'vero_session'
        ORDER BY ordinal_position;
    """)
    for row in cur.fetchall():
        print(f'  {row[0]:18} {row[1]:30} nullable={row[2]:5} default={row[3]}')

    print('\nIndices:')
    cur.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'vero_session';
    """)
    for row in cur.fetchall():
        print(f'  {row[0]}')
        print(f'    {row[1]}')

    cur.close()
    conn.close()
    print('\nPronto.')

if __name__ == '__main__':
    main()
