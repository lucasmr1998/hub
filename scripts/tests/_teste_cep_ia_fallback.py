"""Testa cascata CEP: Camada 1 (regex) + Camada 2 (IA fallback)."""
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

def chega_aguarda_cep(tel):
    post(tel, 'oi'); post(tel, 'Joao Teste IA CEP')

def teste(nome, tel, cep, esperado):
    print(f'\n=== {nome} ===')
    chega_aguarda_cep(tel)
    row = ver(tel)
    print(f'  estado pre-CEP: {row[0] if row else "(novo)"}')
    print(f'  POST {cep!r}...')
    post(tel, cep); time.sleep(3)
    row = ver(tel)
    print(f'  -> nodo_atual={row[0]}')
    print(f'  -> dados={row[1]}')
    print(f'  ESPERADO: {esperado}')

teste('CENARIO 1: regex direto (17010-001 Bauru)',
      '5562900100001', '17010-001',
      'aguarda_plano + cep=17010001 cidade=Bauru')

teste('CENARIO 2: cep dentro de texto (regex limpa)',
      '5562900100002', 'meu cep e 17010001 por favor',
      'aguarda_plano + cep=17010001 cidade=Bauru')

teste('CENARIO 3: CEP em palavras (IA traduz)',
      '5562900110003', 'dezessete mil dez zero zero um',
      'aguarda_plano + cep=17010001 cidade=Bauru (via IA)')

teste('CENARIO 4: nao CEP, e endereco vago (IA rejeita)',
      '5562900100004', 'perto da rodoviaria',
      'aguarda_cep (rejeitado)')
