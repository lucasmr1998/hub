"""Poll read-only ate detectar a migration 0011/0012 aplicada em prod.
Indicador: tabela inbox_motivos_encerramento existe e tem linhas (motivo sistema)."""
import sys, time
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
from pathlib import Path

env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()

DEADLINE = 15 * 60
t0 = time.time()
ult = None
while time.time() - t0 < DEADLINE:
    try:
        c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
            dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
            password=env['PROD_DB_PASSWORD'], connect_timeout=10)
        cur = c.cursor()
        cur.execute("""SELECT EXISTS(SELECT 1 FROM information_schema.tables
WHERE table_name='inbox_motivos_encerramento');""")
        existe = cur.fetchone()[0]
        if existe:
            cur.execute("SELECT COUNT(*) FROM inbox_motivos_encerramento WHERE codigo='auto_inatividade';")
            n_sist = cur.fetchone()[0]
            cur.execute("""SELECT EXISTS(SELECT 1 FROM information_schema.columns
WHERE table_name='inbox_configuracao' AND column_name='encerramento_auto_ativo');""")
            col_ok = cur.fetchone()[0]
            print(f'DEPLOY OK: tabela existe, motivos sistema={n_sist}, coluna config={col_ok}')
            c.close()
            sys.exit(0)
        c.close()
        nova = 'tabela_ainda_nao_existe'
        if nova != ult:
            print(f'[{int(time.time()-t0)}s] {nova}')
            ult = nova
    except Exception as e:
        print(f'erro: {e}')
    time.sleep(30)
print(f'TIMEOUT apos {int((time.time()-t0)/60)}min sem detectar migration')
