"""
Testa validador de CEP em 3 cenarios:
1. CEP formato invalido (asdfgh)
2. CEP formato valido mas inexistente (00000000)
3. CEP valido e existente (01310-100 — Av Paulista SP)
"""
import time
import requests
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
WEBHOOK = f"{env['N8N_BASE_URL'].rstrip('/')}/webhook/vero-orquestrador"

def conn_banco():
    return psycopg2.connect(host='103.199.187.4', port=5434, database='banco_n8n',
                             user='admin', password='Gremio271293@', connect_timeout=10)

def ver_sessao(tel):
    c = conn_banco(); cur = c.cursor()
    cur.execute("SELECT nodo_atual, dados FROM vero_session WHERE telefone = %s;", (tel,))
    row = cur.fetchone()
    cur.close(); c.close()
    return row

def post(tel, msg):
    r = requests.post(WEBHOOK, json={'phone': tel, 'message': msg}, timeout=30)
    return r.status_code, r.text[:50]

def chega_em_aguarda_cep(tel):
    """Manda oi/nome pra chegar em aguarda_cep."""
    for m in ['oi', 'Joao Teste']:
        s, _ = post(tel, m)
        time.sleep(0.5)
    row = ver_sessao(tel)
    print(f'  Estado: nodo_atual={row[0]} dados={row[1]}')

print('\n=== CENARIO 1: CEP formato INVALIDO ===')
TEL1 = '5562900010001'
chega_em_aguarda_cep(TEL1)
print('  POST "asdfgh"...')
post(TEL1, 'asdfgh')
time.sleep(1)
row = ver_sessao(TEL1)
print(f'  -> nodo_atual={row[0]}  dados={row[1]}')
print('  ESPERADO: nodo_atual = aguarda_cep (nao avancou)')

print('\n=== CENARIO 2: CEP formato OK mas INEXISTENTE ===')
TEL2 = '5562900010002'
chega_em_aguarda_cep(TEL2)
print('  POST "00000000"...')
post(TEL2, '00000000')
time.sleep(2)
row = ver_sessao(TEL2)
print(f'  -> nodo_atual={row[0]}  dados={row[1]}')
print('  ESPERADO: nodo_atual = aguarda_cep (CEP nao existe)')

print('\n=== CENARIO 3: CEP VALIDO (Av Paulista SP) ===')
TEL3 = '5562900010003'
chega_em_aguarda_cep(TEL3)
print('  POST "01310-100"...')
post(TEL3, '01310-100')
time.sleep(2)
row = ver_sessao(TEL3)
print(f'  -> nodo_atual={row[0]}  dados={row[1]}')
print('  ESPERADO: nodo_atual = aguarda_plano, dados com cep+cidade=Sao Paulo+estado=SP+bairro')
