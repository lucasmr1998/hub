"""Teste REAL (prod) da distribuicao Flavia: cria lead Palhoca via endpoint,
verifica se a regra 16 atribui Flavia (codigo deployado), limpa tudo no fim.
"""
import sys, json, time
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2, requests
from pathlib import Path
from _n8n_api import N8N

FLAVIA = 23
TEL_TESTE = '5500000000091'

# secret do webhook
n = N8N()
w = n.get_workflow('Df1BgcXdg3HAUZwf')
nodes = {nd['name']: nd for nd in w['nodes']}
secret = None
for p in nodes['Registrar RG Frente Hubtrix']['parameters'].get('headerParameters', {}).get('parameters', []):
    if p.get('name') == 'X-N8N-Webhook-Secret':
        secret = p.get('value')
hdr = {'X-N8N-Webhook-Secret': secret, 'Content-Type': 'application/json'}

env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()

def db():
    c = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
        dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
        password=env['PROD_DB_PASSWORD'], connect_timeout=10)
    return c

# Limpeza previa (caso teste anterior tenha deixado)
def cleanup():
    c = db(); c.autocommit = True; cur = c.cursor()
    cur.execute("SELECT id FROM leads_prospectos WHERE tenant_id=11 AND telefone LIKE %s;", (f'%{TEL_TESTE[2:]}%',))
    lead_ids = [r[0] for r in cur.fetchall()]
    for lid in lead_ids:
        cur.execute("SELECT id FROM crm_oportunidades WHERE lead_id=%s;", (lid,))
        for (oid,) in cur.fetchall():
            cur.execute("DELETE FROM crm_vendas WHERE oportunidade_id=%s;", (oid,))
            cur.execute("DELETE FROM crm_historico_estagio WHERE oportunidade_id=%s;", (oid,))
            cur.execute("DELETE FROM inbox_conversas WHERE oportunidade_id=%s;", (oid,))
            cur.execute("DELETE FROM crm_oportunidades WHERE id=%s;", (oid,))
        cur.execute("DELETE FROM imagens_lead_prospecto WHERE lead_id=%s;", (lid,))
        cur.execute("DELETE FROM crm_vendas WHERE lead_id=%s;", (lid,))
        cur.execute("DELETE FROM leads_prospectos WHERE id=%s;", (lid,))
    c.close()
    return len(lead_ids)

print('Limpeza previa:', cleanup(), 'leads de teste removidos\n')

# 1. Cria lead Palhoca via endpoint receber_lead
print('1. Criando lead de teste (cidade=Palhoca) via endpoint...')
r = requests.post('https://app.hubtrix.com.br/api/public/n8n/lead/', json={
    'tenant_slug': 'tr-carrion', 'telefone': TEL_TESTE,
    'nome_razaosocial': '_TESTE_DISTRIB_FLAVIA', 'cidade': 'Palhoça', 'estado': 'SC',
}, headers=hdr, timeout=25)
print(f'   status={r.status_code} resp={r.text[:200]}')
data = r.json()
lead_id = data.get('lead_id'); oport_id = data.get('oportunidade_id')
print(f'   lead_id={lead_id} oport_id={oport_id}')

time.sleep(1)

# 2. Checa responsavel apos criacao (oport save pode ter disparado engine)
c = db(); c.autocommit = True; cur = c.cursor()
cur.execute("SELECT responsavel_id FROM crm_oportunidades WHERE id=%s;", (oport_id,))
resp1 = cur.fetchone()[0]
print(f'\n2. Apos criar: oport.responsavel_id={resp1} (Flavia={FLAVIA})')

# 3. Se nao atribuiu, dispara engine registrando imagem
if resp1 != FLAVIA:
    print('\n3. Nao atribuiu na criacao. Disparando engine via registro de imagem...')
    rr = requests.post('https://app.hubtrix.com.br/api/public/n8n/lead/imagem/', json={
        'tenant_slug': 'tr-carrion', 'lead_id': lead_id,
        'link_url': 'https://exemplo.com/teste.jpg', 'descricao': 'teste distribuicao',
    }, headers=hdr, timeout=25)
    print(f'   registrar imagem status={rr.status_code}')
    time.sleep(1)
    cur.execute("SELECT responsavel_id FROM crm_oportunidades WHERE id=%s;", (oport_id,))
    resp2 = cur.fetchone()[0]
    print(f'   Apos engine: oport.responsavel_id={resp2} (Flavia={FLAVIA})')
    final = resp2
else:
    final = resp1

cur.execute("SELECT username FROM auth_user WHERE id=%s;", (final,)) if final else None
uname = cur.fetchone()[0] if final else None
print(f'\n=== RESULTADO ===')
print(f'  responsavel final: {final} ({uname})')
print(f'  {"PASSOU — distribuicao Flavia funciona!" if final==FLAVIA else "NAO atribuiu Flavia"}')

c.close()
# 4. Cleanup
print(f'\n4. Limpeza final: {cleanup()} leads removidos')
