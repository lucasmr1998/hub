"""READ-ONLY prod (tenant 11): por que o lead de Palhoça nao foi pra Flavia.
Conversa 298 -> lead/oportunidade -> responsavel CRM vs agente inbox. Quem eh Flavia.
"""
import sys
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2
from pathlib import Path

env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
cur = c.cursor()

cur.execute("SELECT id, lead_id, oportunidade_id, agente_id, tenant_id FROM inbox_conversas WHERE id=298;")
conv = cur.fetchone()
print('conversa 298:', dict(zip(['id','lead_id','oportunidade_id','agente_id','tenant_id'], conv)))
lead_id, oport_id, agente_id, tid = conv[1], conv[2], conv[3], conv[4]

def uname(uid):
    if not uid: return None
    cur.execute("SELECT first_name, last_name, username FROM auth_user WHERE id=%s;", (uid,))
    r = cur.fetchone()
    return f"{r[0]} {r[1]}".strip() or r[2] if r else f'id{uid}'

print('agente da conversa:', agente_id, '->', uname(agente_id))

if lead_id:
    cur.execute("SELECT id, nome_razaosocial, cidade, estado, id_origem FROM leads_prospectos WHERE id=%s;", (lead_id,))
    print('lead:', cur.fetchone())
if oport_id:
    cur.execute("SELECT id, titulo, responsavel_id, estagio_id, data_criacao FROM crm_oportunidades WHERE id=%s;", (oport_id,))
    o = cur.fetchone()
    print('oportunidade:', o)
    print('responsavel da oportunidade:', o[2], '->', uname(o[2]))

# quem eh Flavia no tenant 11
cur.execute("""SELECT u.id, u.first_name, u.last_name FROM auth_user u
               JOIN sistema_perfil_usuario p ON p.user_id=u.id
               WHERE p.tenant_id=%s AND (u.first_name ILIKE %s OR u.last_name ILIKE %s);""",
            (tid, '%flavia%', '%flavia%'))
print('\nFlavia(s) no tenant 11:', cur.fetchall())
c.close()
