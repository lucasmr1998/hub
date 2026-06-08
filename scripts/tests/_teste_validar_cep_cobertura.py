"""
Testa CEP + cobertura em 3 cenarios:
1. CEP de cidade ATENDIDA (Bauru/SP — cadastrada no banco)
2. CEP de cidade SP NAO cadastrada (Santos/SP — nao esta na lista do tr-carrion)
3. CEP fora de SP (Goiania/GO)
"""
import time
import requests
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
WEBHOOK = f"{env['N8N_BASE_URL'].rstrip('/')}/webhook/vero-orquestrador"
SECRET = env['HUBTRIX_N8N_WEBHOOK_SECRET']

def conn_banco():
    return psycopg2.connect(host='103.199.187.4', port=5434, database='banco_n8n',
                             user='admin', password='Gremio271293@', connect_timeout=10)

def ver_sessao(tel):
    c = conn_banco(); cur = c.cursor()
    cur.execute("SELECT nodo_atual, dados FROM vero_session WHERE telefone = %s;", (tel,))
    row = cur.fetchone(); cur.close(); c.close(); return row

def post(tel, msg):
    r = requests.post(WEBHOOK, json={'phone': tel, 'message': msg}, timeout=30)
    return r.status_code

def chega_aguarda_cep(tel):
    for m in ['oi', 'Joao Teste']:
        post(tel, m); time.sleep(0.4)

def teste(nome, tel, cep, esperado):
    print(f'\n=== {nome} (CEP {cep}) ===')
    chega_aguarda_cep(tel)
    post(tel, cep); time.sleep(2)
    row = ver_sessao(tel)
    print(f'  -> nodo_atual={row[0]}')
    print(f'  -> dados={row[1]}')
    print(f'  ESPERADO: {esperado}')

# Primeiro testa o endpoint direto pra confirmar que ta no ar
print('\n=== Sanity check endpoint /viabilidade/ ===')
r = requests.post('https://app.hubtrix.com.br/api/public/n8n/viabilidade/',
                  headers={'X-N8N-Webhook-Secret': SECRET, 'Content-Type': 'application/json'},
                  json={'tenant_slug': 'tr-carrion', 'cidade': 'Bauru', 'estado': 'SP'},
                  timeout=15)
print(f'  status={r.status_code}')
print(f'  body={r.text[:500]}')

teste('CENARIO 1: Bauru/SP (ATENDIDA)',         '5562900020001', '17010-001', 'aguarda_plano (atendido)')
teste('CENARIO 2: Santos/SP (nao cadastrada)',  '5562900020002', '11013-040', 'aguarda_cep (sem cobertura)')
teste('CENARIO 3: Goiania/GO (outra UF)',       '5562900020003', '74000-000', 'aguarda_cep (sem cobertura)')
