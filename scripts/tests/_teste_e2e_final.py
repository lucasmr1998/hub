"""Teste E2E final do orquestrador Vero — conversa completa com cliente fala livre."""
import time
import requests
import psycopg2
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
WEBHOOK = f"{env['N8N_BASE_URL'].rstrip('/')}/webhook/vero-orquestrador"

def conn_banco():
    return psycopg2.connect(host='103.199.187.4', port=5434, database='banco_n8n',
                             user='admin', password='Gremio271293@', connect_timeout=10)

def ver(tel):
    c = conn_banco(); cur = c.cursor()
    cur.execute("SELECT nodo_atual, dados FROM vero_session WHERE telefone = %s;", (tel,))
    r = cur.fetchone(); cur.close(); c.close(); return r

def post(tel, msg):
    requests.post(WEBHOOK, json={'phone': tel, 'message': msg}, timeout=30); time.sleep(0.5)

TEL = '5562900300001'

print('=== Conversa simulada cliente Vero TR Carrion ===\n')

print('Cliente: oi')
post(TEL, 'oi')
print('Cliente: Maria Aparecida da Silva')
post(TEL, 'Maria Aparecida da Silva')
print('Cliente: meu cep e 17010001 obrigada')
post(TEL, 'meu cep e 17010001 obrigada')
time.sleep(2)
print('Cliente: quero o de 800 com disney')
post(TEL, 'quero o de 800 com disney')
time.sleep(3)
print('Cliente: maria silva arroba gmail ponto com')
post(TEL, 'maria silva arroba gmail ponto com')
time.sleep(3)

row = ver(TEL)
print(f'\n=== FINAL ===')
print(f'nodo_atual={row[0]}')
print(f'dados={row[1]}')
