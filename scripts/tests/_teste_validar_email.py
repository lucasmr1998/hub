"""
Testa validador de email em 2 cenarios:

CENARIO 1: email INVALIDO -> nao deve avancar, deve manter aguarda_email
CENARIO 2: email VALIDO   -> avanca pra concluido + envia pro Hubtrix
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
    return r.status_code, r.text[:100]

def percorre_ate_email(tel):
    """Manda oi/nome/cep/plano pra chegar no estado aguarda_email."""
    for m in ['oi', 'Joao Teste', '74000-000', 'Plano 1GB']:
        s, b = post(tel, m)
        print(f'  POST {m!r:20} -> {s} {b!r}')
        time.sleep(0.5)

print('\n=== CENARIO 1: email INVALIDO ===')
TEL1 = '5562900003333'
percorre_ate_email(TEL1)
print(f'  Estado apos plano:')
row = ver_sessao(TEL1)
print(f'    nodo_atual={row[0]} dados={row[1]}')

print('  Mandando email INVALIDO (asdfgh)...')
s, b = post(TEL1, 'asdfgh')
print(f'    -> {s} {b!r}')
time.sleep(1)

print(f'  Estado apos email invalido:')
row = ver_sessao(TEL1)
print(f'    nodo_atual={row[0]} dados={row[1]}')
print('  ESPERADO: nodo_atual ainda = aguarda_email')

print('  Agora mandando email VALIDO no mesmo telefone...')
s, b = post(TEL1, 'joao.bom@gmail.com')
print(f'    -> {s} {b!r}')
time.sleep(1)
row = ver_sessao(TEL1)
print(f'  Estado final: nodo_atual={row[0]} dados={row[1]}')
print('  ESPERADO: nodo_atual = concluido, dados.email = joao.bom@gmail.com')


print('\n=== CENARIO 2: email valido direto ===')
TEL2 = '5562900004444'
percorre_ate_email(TEL2)
print(f'  Estado apos plano:')
row = ver_sessao(TEL2)
print(f'    nodo_atual={row[0]} dados={row[1]}')

print('  Mandando email VALIDO direto...')
s, b = post(TEL2, 'maria.cliente@vero.net.br')
print(f'    -> {s} {b!r}')
time.sleep(1)
row = ver_sessao(TEL2)
print(f'  Estado final: nodo_atual={row[0]} dados={row[1]}')
print('  ESPERADO: nodo_atual = concluido, dados.email = maria.cliente@vero.net.br')
