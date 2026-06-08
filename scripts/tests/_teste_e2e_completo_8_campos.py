"""E2E completo: nome, cep, numero, complemento, plano, cpf, data_nasc, email."""
import time
import sys
import io
import json
import requests
import psycopg2
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = dotenv_values('.env.n8n')
WEBHOOK = f"{env['N8N_BASE_URL'].rstrip('/')}/webhook/vero-orquestrador"

def conn_banco():
    return psycopg2.connect(host='103.199.187.4', port=5434, database='banco_n8n',
                             user='admin', password='Gremio271293@', connect_timeout=10)

def ver(tel):
    c = conn_banco(); cur = c.cursor()
    cur.execute("SELECT nodo_atual, dados FROM vero_session WHERE telefone = %s;", (tel,))
    r = cur.fetchone(); cur.close(); c.close()
    return r if r else ('(novo)', {})

def post(tel, msg):
    requests.post(WEBHOOK, json={'phone': tel, 'message': msg}, timeout=30)

TEL = '5511912345678'  # telefone fresh

CONVERSA = [
    ('oi',                                              'cumprimento'),
    ('Maria Aparecida da Silva',                        'nome'),
    ('17013-000',                                       'CEP de Bauru'),
    ('120',                                             'numero da casa'),
    ('apto 304',                                        'complemento'),
    ('3',                                               'escolhe plano numero 3'),
    ('123.456.789-09',                                  'CPF formatado'),  # CPF teste valido
    ('15/03/1985',                                      'data de nascimento'),
    ('maria.silva@email.com',                           'email'),
]

print('=' * 75)
print('  E2E CONVERSA COMPLETA — 8 CAMPOS')
print('=' * 75)
print(f'  Telefone: {TEL}\n')

for i, (msg, descr) in enumerate(CONVERSA, 1):
    estado_antes = ver(TEL)
    post(TEL, msg)
    time.sleep(2.5)
    estado_depois = ver(TEL)
    print(f'TURNO {i}: {msg!r} ({descr})')
    print(f'  {estado_antes[0]} -> {estado_depois[0]}')
    if estado_depois[1]:
        print(f'  dados: {json.dumps(estado_depois[1], ensure_ascii=False)}')
    print()

print('=' * 75)
final = ver(TEL)
print(f'  Estado final: {final[0]}')
print(f'  Lead completo:')
for k, v in sorted(final[1].items()):
    print(f'    {k:20} = {v}')
