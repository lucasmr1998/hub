"""DRY-RUN: testa quantas imagens perdidas o Uazapi ainda recupera.
Nao escreve nada. So chama POST /message/download e ve se retorna fileURL.
"""
import sys, json
import psycopg2, requests
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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
token = cfg.get('token', '')
base = base.rstrip('/')

cur.execute("""
SELECT m.conversa_id, c.lead_id, m.identificador_externo, m.data_envio
FROM inbox_mensagens m JOIN inbox_conversas c ON c.id=m.conversa_id
WHERE c.tenant_id=11 AND m.remetente_tipo='contato'
  AND m.tipo_conteudo IN ('imagem','arquivo','video')
  AND m.identificador_externo <> ''
  AND COALESCE((SELECT COUNT(*) FROM imagens_lead_prospecto i WHERE i.lead_id=c.lead_id),0)=0
ORDER BY m.data_envio DESC;
""")
imgs = cur.fetchall()
cur.close(); conn.close()

print(f'Testando {len(imgs)} imagens no Uazapi...\n')
ok, expirada, erro = 0, 0, 0
headers = {'token': token, 'Content-Type': 'application/json'}
for conv, lead, msgid, dt in imgs:
    try:
        r = requests.post(f'{base}/message/download', json={'id': msgid},
                          headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            furl = data.get('fileURL', '')
            if furl:
                ok += 1
                status = 'RECUPERAVEL'
            else:
                expirada += 1
                status = f'sem fileURL ({json.dumps(data)[:60]})'
        else:
            erro += 1
            status = f'HTTP {r.status_code}: {r.text[:60]}'
    except Exception as e:
        erro += 1
        status = f'EXC {e}'
    print(f'  conv={conv} lead={lead} {str(dt)[:16]} -> {status}')

print(f'\n=== RESUMO ===')
print(f'  Recuperaveis: {ok}')
print(f'  Sem fileURL/expiradas: {expirada}')
print(f'  Erro: {erro}')
print(f'  Total: {len(imgs)}')
