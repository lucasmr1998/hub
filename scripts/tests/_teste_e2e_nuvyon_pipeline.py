"""Teste E2E (prod) da integracao Nuvyon: simula o bot chamando /lead/ com
sinais e verifica o pipeline andar. Limpa no fim.
"""
import sys, json, time
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2, requests
from pathlib import Path
from _n8n_api import N8N

TEL = '5500000000099'
LEAD_URL = 'https://app.hubtrix.com.br/api/public/n8n/lead/'

# secret
n = N8N()
w = n.get_workflow('Df1BgcXdg3HAUZwf')
nodes = {nd['name']: nd for nd in w['nodes']}
secret = next(p['value'] for p in nodes['Registrar RG Frente Hubtrix']['parameters']['headerParameters']['parameters'] if p['name'] == 'X-N8N-Webhook-Secret')
hdr = {'X-N8N-Webhook-Secret': secret, 'Content-Type': 'application/json'}

env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()

def db():
    return psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
        dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
        password=env['PROD_DB_PASSWORD'], connect_timeout=10)

def cleanup():
    c = db(); c.autocommit = True; cur = c.cursor()
    cur.execute("SELECT id FROM leads_prospectos WHERE tenant_id=12 AND telefone LIKE %s;", (f'%{TEL[2:]}%',))
    for (lid,) in cur.fetchall():
        cur.execute("SELECT id FROM crm_oportunidades WHERE lead_id=%s;", (lid,))
        for (oid,) in cur.fetchall():
            cur.execute("DELETE FROM crm_oportunidades_tags WHERE oportunidadevenda_id=%s;", (oid,))
            cur.execute("DELETE FROM crm_vendas WHERE oportunidade_id=%s;", (oid,))
            cur.execute("DELETE FROM crm_historico_estagio WHERE oportunidade_id=%s;", (oid,))
            cur.execute("DELETE FROM crm_oportunidades WHERE id=%s;", (oid,))
        cur.execute("DELETE FROM historico_contato WHERE lead_id=%s;", (lid,))
        cur.execute("DELETE FROM crm_vendas WHERE lead_id=%s;", (lid,))
        cur.execute("DELETE FROM imagens_lead_prospecto WHERE lead_id=%s;", (lid,))
        cur.execute("DELETE FROM leads_prospectos WHERE id=%s;", (lid,))
    c.close()

print('Cleanup previo...'); cleanup()

def chamar(label, extra):
    body = {'tenant_slug': 'nuvyon', 'telefone': TEL,
            'nome_razaosocial': '_TESTE_NUVYON_PIPE', 'cidade': 'Mococa', 'estado': 'SP'}
    body.update(extra)
    r = requests.post(LEAD_URL, json=body, headers=hdr, timeout=25)
    j = r.json() if r.status_code in (200, 201) else {}
    est = j.get('estagio_nome')
    print(f'  {label:35s} -> {r.status_code} estagio={est!r}')
    if r.status_code not in (200, 201):
        print(f'      resp: {r.text[:150]}')
    time.sleep(0.5)
    return j

print('\nSimulando jornada do bot:')
chamar('1. lead novo', {})
chamar('2. historico resposta', {'historico_status': 'resposta'})
chamar('3. tag Endereço', {'tags': ['Endereço']})
chamar('4. id_plano_rp', {'lead_campos': {'id_plano_rp': 'PLANO123'}})
chamar('5. tag Comercial', {'tags': ['Comercial']})
chamar('6. status aguardando_assinatura', {'lead_campos': {'status_api': 'aguardando_assinatura'}})
chamar('7. tag Assinado', {'tags': ['Assinado']})

print('\nCleanup final...'); cleanup()
print('OK.')
