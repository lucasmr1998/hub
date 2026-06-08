"""
Testa cascata Email com 3 cenarios:
1. Email valido normal — passa pela Camada 1 (regex), nao chama IA
2. Email informal — Camada 1 falha, IA normaliza ("joao gmail com" -> "joao@gmail.com")
3. Email lixo — ambas as camadas rejeitam, fica em aguarda_email
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

def ver(tel):
    c = conn_banco(); cur = c.cursor()
    cur.execute("SELECT nodo_atual, dados FROM vero_session WHERE telefone = %s;", (tel,))
    r = cur.fetchone(); cur.close(); c.close(); return r

def post(tel, msg):
    requests.post(WEBHOOK, json={'phone': tel, 'message': msg}, timeout=30); time.sleep(0.5)

def percorre_ate_email(tel):
    """Manda nome/cep/plano pra chegar em aguarda_email."""
    post(tel, 'oi')
    post(tel, 'Joao Teste IA')
    post(tel, '17010-001')  # Bauru — cidade atendida
    time.sleep(1)
    post(tel, 'Plano 800')

def teste(nome, tel, email_input, esperado):
    print(f'\n=== {nome} ===')
    percorre_ate_email(tel)
    row = ver(tel)
    print(f'  estado pre-email: {row[0] if row else "(sem sessao)"}')
    if row and row[0] != 'aguarda_email':
        print(f'  AVISO: nao chegou em aguarda_email, ta em {row[0]}')
    print(f'  POST {email_input!r}...')
    post(tel, email_input)
    time.sleep(3)  # IA leva ~1-2s
    row = ver(tel)
    print(f'  -> nodo_atual={row[0]}')
    print(f'  -> dados={row[1]}')
    print(f'  ESPERADO: {esperado}')

teste('CENARIO 1: email valido normal (Camada 1 regex)',
      '5562900090001', 'joao@gmail.com',
      'concluido + email=joao@gmail.com (sem IA)')

teste('CENARIO 2: email informal (Camada 1 falha, IA normaliza)',
      '5562900090002', 'joao gmail com',
      'concluido + email=joao@gmail.com (normalizado pela IA)')

teste('CENARIO 3: lixo (ambas falham)',
      '5562900090003', 'asdfgh',
      'aguarda_email (rejeitado pelas duas camadas)')
