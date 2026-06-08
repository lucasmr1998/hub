"""READ-ONLY prod: histórico de uma conversa do Inbox por telefone.
Acha a conversa (qualquer tenant), mostra metadados + mensagens em ordem.
"""
import sys
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
from pathlib import Path

TEL = '554899962661'
env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
cur = c.cursor()

def cols(t):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position;", (t,))
    return [r[0] for r in cur.fetchall()]

ccols = cols('inbox_conversas')
print('inbox_conversas cols:', ccols)
telcol = next((x for x in ('telefone','contato_telefone','numero','identificador','contato') if x in ccols), None)
print('coluna telefone:', telcol)

cur.execute(f"""SELECT id, tenant_id, {telcol}, contato_nome, modo_atendimento, status,
                       agente_id, data_abertura
                FROM inbox_conversas WHERE {telcol} LIKE %s ORDER BY data_abertura;""",
            (f'%{TEL[-10:]}%',))
convs = cur.fetchall()
print(f'\nConversas encontradas: {len(convs)}')
for r in convs:
    print(f'  id={r[0]} tenant={r[1]} tel={r[2]} nome={r[3]!r} modo={r[4]} status={r[5]} agente_id={r[6]} aberta={r[7]}')

if not convs:
    print('Nenhuma conversa.'); sys.exit(0)

cid = convs[-1][0]  # mais recente
mcols = cols('inbox_mensagens')
print('\ninbox_mensagens cols:', mcols)
datacol = next((x for x in ('data_criacao','criado_em','timestamp','data') if x in mcols), 'id')
cur.execute(f"""SELECT * FROM inbox_mensagens WHERE conversa_id=%s ORDER BY {datacol};""", (cid,))
rows = cur.fetchall()
idx = {n: i for i, n in enumerate(mcols)}
print(f'\n=== {len(rows)} mensagens (conversa {cid}) ===')
for r in rows:
    def g(name): return r[idx[name]] if name in idx else ''
    dirr = g('direcao') or g('tipo') or g('remetente')
    cont = str(g('conteudo') or g('mensagem') or g('texto') or '')
    tipo = g('tipo_conteudo') or g('tipo')
    print(f"  [{g(datacol)}] ({dirr}|{tipo}) {cont[:160]}")
c.close()
