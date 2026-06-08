"""Testa validador de PLANO em 4 cenarios."""
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

def chega_aguarda_plano(tel):
    post(tel, 'oi')
    post(tel, 'Joao Teste Plano')
    post(tel, '17010-001')   # Bauru / grupo B
    time.sleep(2)

def teste(nome, tel, escolha_plano, esperado):
    print(f'\n=== {nome} ===')
    chega_aguarda_plano(tel)
    row = ver(tel)
    print(f'  estado pre-plano: {row[0] if row else "?"}')
    print(f'  POST {escolha_plano!r}...')
    post(tel, escolha_plano)
    time.sleep(3)
    row = ver(tel)
    print(f'  -> nodo_atual={row[0]}')
    print(f'  -> dados={row[1]}')
    print(f'  ESPERADO: {esperado}')

teste('CENARIO 1: numero direto "3" (Camada 1)',
      '5562900200001', '3',
      'aguarda_email + plano_id=B3')

teste('CENARIO 2: velocidade unica "550" (Camada 1 — Bauru tem 2 planos 550)',
      '5562900200002', '550',
      'aguarda_plano OU aguarda_email (depende de IA aceitar ambiguo)')

teste('CENARIO 3: fala livre "800 com disney" (Camada 2 IA)',
      '5562900200003', 'quero o de 800 com disney',
      'aguarda_email + plano_id de algum 800+Disney')

teste('CENARIO 4: lixo "xyz" (rejeita)',
      '5562900200004', 'xyz',
      'aguarda_plano (rejeitado)')
