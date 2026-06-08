"""Valida Familia 1: chama /api/leads/registrar/ com o Bearer token Nuvyon
(simulando o no CreateLead repointado), confere lead criado no tenant 12, limpa.
"""
import sys
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2, requests
from pathlib import Path

TEL = '5500000000077'
env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()

def db():
    return psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
        dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
        password=env['PROD_DB_PASSWORD'], connect_timeout=10)

# token (nao ecoa)
c = db(); c.autocommit = True; cur = c.cursor()
cur.execute("SELECT api_token FROM integracoes_api WHERE id=20;")
token = cur.fetchone()[0]

def cleanup():
    cur.execute("SELECT id FROM leads_prospectos WHERE tenant_id=12 AND telefone LIKE %s;", (f'%{TEL[2:]}%',))
    for (lid,) in cur.fetchall():
        cur.execute("SELECT id FROM crm_oportunidades WHERE lead_id=%s;", (lid,))
        for (oid,) in cur.fetchall():
            cur.execute("DELETE FROM crm_oportunidades_tags WHERE oportunidadevenda_id=%s;", (oid,))
            cur.execute("DELETE FROM crm_vendas WHERE oportunidade_id=%s;", (oid,))
            cur.execute("DELETE FROM crm_historico_estagio WHERE oportunidade_id=%s;", (oid,))
            cur.execute("DELETE FROM crm_oportunidades WHERE id=%s;", (oid,))
        cur.execute("DELETE FROM crm_vendas WHERE lead_id=%s;", (lid,))
        cur.execute("DELETE FROM leads_prospectos WHERE id=%s;", (lid,))

cleanup()

# 1. sem token -> deve dar 401
r0 = requests.post('https://app.hubtrix.com.br/api/leads/registrar/',
    json={'nome_razaosocial': '_T', 'telefone': TEL}, timeout=20)
print(f'1. SEM token -> {r0.status_code} (esperado 401/403)')

# 2. com token Nuvyon -> deve criar lead no tenant 12
r = requests.post('https://app.hubtrix.com.br/api/leads/registrar/',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    json={'nome_razaosocial': '_TESTE_REPOINT_F1', 'telefone': TEL,
          'cidade': 'Mococa', 'estado': 'SP', 'origem': 'whatsapp_matrix'}, timeout=20)
print(f'2. COM token -> {r.status_code} resp={r.text[:160]}')

# 3. confere no banco
cur.execute("""SELECT l.id, l.tenant_id, l.nome_razaosocial,
  (SELECT COUNT(*) FROM crm_oportunidades o WHERE o.lead_id=l.id) AS oports
  FROM leads_prospectos l WHERE l.telefone LIKE %s;""", (f'%{TEL[2:]}%',))
for row in cur.fetchall():
    print(f'3. lead id={row[0]} tenant={row[1]} (esperado 12) nome={row[2]!r} oports={row[3]}')

cleanup()
print('\nCleanup ok.')
c.close()
