"""
C.3: Agregacao multimensagem (Matrix-style).

Cria tabela vero_message_buffer no banco_n8n.
Cada msg chegando: INSERT + WAIT 2s + checa se eh a mais recente.
Se eh a mais recente: agrega todas, processa, deleta buffer.
Se nao eh: descarta (proxima msg processa).
"""
import psycopg2

conn = psycopg2.connect(host='103.199.187.4', port=5434, database='banco_n8n',
                         user='admin', password='Gremio271293@', connect_timeout=10)
conn.autocommit = True
cur = conn.cursor()

# Cria tabela buffer
cur.execute("""
CREATE TABLE IF NOT EXISTS vero_message_buffer (
    id           BIGSERIAL PRIMARY KEY,
    telefone     VARCHAR(20) NOT NULL,
    conteudo     TEXT NOT NULL,
    tem_imagem   BOOLEAN DEFAULT FALSE,
    url_imagem   TEXT DEFAULT '',
    recebida_em  TIMESTAMP NOT NULL DEFAULT NOW(),
    processada   BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_vero_buffer_tel_recebida
    ON vero_message_buffer (telefone, recebida_em DESC) WHERE processada = FALSE;
""")
print('Tabela vero_message_buffer criada')

cur.execute("SELECT COUNT(*) FROM vero_message_buffer;")
print(f'Linhas iniciais: {cur.fetchone()[0]}')
cur.close(); conn.close()
