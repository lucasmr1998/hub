"""
Simula 4 mensagens em sequencia no webhook do N8N (sem Wazapi).
Cada POST representa uma mensagem do cliente:
  1. "oi"               -> estado inicio       -> bot pede nome
  2. "Joao Silva"       -> aguarda_nome        -> bot pede cep
  3. "74000-000"        -> aguarda_cep         -> bot pede plano
  4. "email@x.com"      -> aguarda_email       -> concluido -> dispara POST pro Hubtrix

Cada chamada e independente. O N8N carrega o estado do Postgres a cada mensagem.
"""
import time
import json
import requests
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
WEBHOOK = f'{BASE}/webhook/vero-orquestrador'

TELEFONE = '5562933334444'  # 4a rodada — apos fix do nodo Hubtrix
MENSAGENS = [
    'oi',
    'Joao Silva da Conceicao',
    '74000-000',
    'Plano 500 Mega',
    'joao.teste@example.com',
]

print(f'Webhook: {WEBHOOK}')
print(f'Telefone simulado: {TELEFONE}\n')

for i, msg in enumerate(MENSAGENS, 1):
    payload = {
        'phone': TELEFONE,
        'message': msg,
    }
    print(f'=== Mensagem {i}/{len(MENSAGENS)}: {msg!r} ===')
    try:
        r = requests.post(WEBHOOK, json=payload, timeout=30)
        print(f'  status={r.status_code}')
        try:
            print(f'  body={json.dumps(r.json(), indent=2, ensure_ascii=False)[:500]}')
        except Exception:
            print(f'  body={r.text[:500]}')
    except Exception as e:
        print(f'  ERR: {e}')
    print()
    time.sleep(1)  # da um respiro entre chamadas

# Limpa sessao depois pra deixar pronto pro proximo teste
print('Limpando sessao de teste no banco_n8n...')
import psycopg2
conn = psycopg2.connect(
    host='103.199.187.4', port=5434,
    database='banco_n8n', user='admin', password='Gremio271293@',
    connect_timeout=10,
)
cur = conn.cursor()
cur.execute("SELECT telefone, nodo_atual, dados FROM vero_session WHERE telefone = %s;", (TELEFONE,))
row = cur.fetchone()
if row:
    print(f'  Sessao final: telefone={row[0]} nodo_atual={row[1]}')
    print(f'  dados={json.dumps(row[2], indent=2, ensure_ascii=False)}')
else:
    print('  Sessao nao encontrada (nodo nao gravou?)')
cur.close()
conn.close()
