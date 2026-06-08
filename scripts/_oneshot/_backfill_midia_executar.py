"""Backfill REAL: recupera as 42 imagens perdidas e registra no Hubtrix.

Pra cada imagem:
  1. Uazapi POST /message/download -> fileURL decriptada
  2. POST Hubtrix /api/public/n8n/lead/imagem/ (cria ImagemLeadProspecto)
     -> dispara signal engine_apos_imagem -> automacao 'Criar Venda'

Secret do webhook e creds Uazapi sao lidos em runtime (N8N + DB), sem hardcode.
ESCREVE EM PROD. Autorizado pelo usuario (opcao 2).
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import psycopg2, requests
from pathlib import Path
from _n8n_api import N8N

HUBTRIX_IMG = 'https://app.hubtrix.com.br/api/public/n8n/lead/imagem/'

# 1. Secret do webhook (do no N8N)
n = N8N()
w = n.get_workflow('Df1BgcXdg3HAUZwf')
nodes = {nd['name']: nd for nd in w['nodes']}
secret = None
for p in nodes['Registrar RG Frente Hubtrix']['parameters'].get('headerParameters', {}).get('parameters', []):
    if p.get('name') == 'X-N8N-Webhook-Secret':
        secret = p.get('value')
if not secret:
    sys.exit('Secret nao encontrado')

# 2. Creds Uazapi + lista de imagens (DB)
env = {}
for l in Path('.env.prod_readonly').read_text(encoding='utf-8').splitlines():
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); env[k.strip()] = v.strip()
conn = psycopg2.connect(host=env['PROD_DB_HOST'], port=env['PROD_DB_PORT'],
    dbname=env['PROD_DB_NAME'], user=env['PROD_DB_USER'],
    password=env['PROD_DB_PASSWORD'], connect_timeout=10)
conn.set_session(readonly=True, autocommit=True)
cur = conn.cursor()
cur.execute("SELECT base_url, configuracoes_extras FROM integracoes_api WHERE id=19;")
base, cfg = cur.fetchone()
cfg = cfg if isinstance(cfg, dict) else json.loads(cfg or '{}')
uaz_token = cfg.get('token', ''); base = base.rstrip('/')

cur.execute("""
SELECT c.lead_id, m.identificador_externo, m.tipo_conteudo, m.data_envio, m.arquivo_nome
FROM inbox_mensagens m JOIN inbox_conversas c ON c.id=m.conversa_id
WHERE c.tenant_id=11 AND m.remetente_tipo='contato'
  AND m.tipo_conteudo IN ('imagem','arquivo','video')
  AND m.identificador_externo <> ''
  AND COALESCE((SELECT COUNT(*) FROM imagens_lead_prospecto i WHERE i.lead_id=c.lead_id),0)=0
ORDER BY m.data_envio ASC;
""")
imgs = cur.fetchall()
cur.close(); conn.close()
print(f'Imagens a recuperar: {len(imgs)}\n')

uaz_h = {'token': uaz_token, 'Content-Type': 'application/json'}
hub_h = {'X-N8N-Webhook-Secret': secret, 'Content-Type': 'application/json'}
ok, falha = 0, 0
vendas_leads = set()
for lead_id, msgid, tipo, dt, nome in imgs:
    try:
        r = requests.post(f'{base}/message/download', json={'id': msgid}, headers=uaz_h, timeout=25)
        furl = (r.json() or {}).get('fileURL', '') if r.status_code == 200 else ''
        if not furl:
            falha += 1; print(f'  lead={lead_id} {str(dt)[:16]} FALHA download'); continue
        desc = f'Documento recuperado ({tipo}, {str(dt)[:10]})'
        rr = requests.post(HUBTRIX_IMG, json={
            'tenant_slug': 'tr-carrion', 'lead_id': lead_id,
            'link_url': furl, 'descricao': desc,
        }, headers=hub_h, timeout=25)
        if rr.status_code == 201:
            ok += 1; vendas_leads.add(lead_id)
            print(f'  lead={lead_id} {str(dt)[:16]} OK imagem_id={rr.json().get("imagem_id")}')
        else:
            falha += 1; print(f'  lead={lead_id} {str(dt)[:16]} FALHA registro {rr.status_code}: {rr.text[:80]}')
    except Exception as e:
        falha += 1; print(f'  lead={lead_id} EXC {e}')

print(f'\n=== RESUMO ===\n  Registradas: {ok}\n  Falhas: {falha}\n  Leads afetados: {len(vendas_leads)}')
