"""
Roda uma conversa completa e mostra resumo turno a turno:
- O que o cliente disse
- Estado antes / depois
- Camada que validou (1 regex ou 2 IA)
- Dados acumulados
"""
import time
import json
import sys
import io
import requests
import psycopg2
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = dotenv_values('.env.n8n')
WEBHOOK = f"{env['N8N_BASE_URL'].rstrip('/')}/webhook/vero-orquestrador"
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']

def conn_banco():
    return psycopg2.connect(host='103.199.187.4', port=5434, database='banco_n8n',
                             user='admin', password='Gremio271293@', connect_timeout=10)

def ver(tel):
    c = conn_banco(); cur = c.cursor()
    cur.execute("SELECT nodo_atual, dados FROM vero_session WHERE telefone = %s;", (tel,))
    r = cur.fetchone(); cur.close(); c.close()
    return r if r else ('(sem sessao)', {})

def post(tel, msg):
    requests.post(WEBHOOK, json={'phone': tel, 'message': msg}, timeout=30)

def ultima_exec():
    """Pega a ultima execution e identifica qual camada validou."""
    r = requests.get(f'{BASE}/api/v1/executions', params={'workflowId': 'Df1BgcXdg3HAUZwf', 'limit': 1},
                     headers={'X-N8N-API-KEY': KEY}, timeout=10)
    if not r.ok: return None
    execs = r.json().get('data', [])
    if not execs: return None
    eid = execs[0]['id']
    r2 = requests.get(f'{BASE}/api/v1/executions/{eid}?includeData=true',
                      headers={'X-N8N-API-KEY': KEY}, timeout=15)
    d = r2.json()
    run = d.get('data', {}).get('resultData', {}).get('runData', {})
    nodes = list(run.keys())

    # Identifica caminho
    if 'IA Validator Universal' in nodes:
        ria = run.get('ResultadoIA', [{}])[0].get('data', {}).get('main', [[{}]])[0]
        resp = ria[0]['json'].get('response', {}) if ria else {}
        return {
            'camada': 'IA (Camada 2)',
            'ia_ok': resp.get('answerIsCorrect'),
            'formatted': resp.get('formattedValue'),
            'errorMsg': resp.get('errorMessage'),
            'nodes_count': len(nodes),
        }
    elif any(n.startswith('Validar') or n.startswith('Formato') or n.startswith('Email V') or n.startswith('Plano V') for n in nodes):
        return {'camada': 'Regex (Camada 1)', 'nodes_count': len(nodes)}
    else:
        return {'camada': 'Step direto', 'nodes_count': len(nodes)}

# Conversa simulada
TEL = '5562955667788'  # telefone 100% fresh

conversa = [
    ('oi', 'cumprimenta'),
    ('Lucas Carrion da Silva', 'nome'),
    ('17013-000', 'CEP de Bauru'),
    ('quero o mais barato com chip', 'plano em linguagem natural'),
    ('lucas carrion arroba vero ponto net ponto br', 'email informal'),
]

print('=' * 70)
print('  VALIDACAO E2E — ORQUESTRADOR VERO TR CARRION')
print('=' * 70)
print(f'  Telefone: {TEL}\n')

for i, (msg, descr) in enumerate(conversa, 1):
    estado_antes = ver(TEL)
    post(TEL, msg)
    time.sleep(3.5)  # da tempo da IA responder
    estado_depois = ver(TEL)
    info = ultima_exec()

    print(f'─── TURNO {i} ──────────────────────────────────────────────────')
    print(f'Cliente: {msg!r}  ({descr})')
    print(f'  Estado: {estado_antes[0]:18} -> {estado_depois[0]}')
    if info:
        print(f'  Validacao: {info["camada"]}  (nodos executados: {info["nodes_count"]})')
        if info.get('formatted'):
            print(f'  IA normalizou pra: {info["formatted"]!r}')
        if info.get('errorMsg'):
            print(f'  Mensagem da IA: {info["errorMsg"]!r}')
    print(f'  Dados acumulados: {json.dumps(estado_depois[1], ensure_ascii=False)}')
    print()

print('=' * 70)
print('  RESUMO FINAL')
print('=' * 70)
final = ver(TEL)
print(f'  Estado final: {final[0]}')
print(f'  Dados completos:')
for k, v in final[1].items():
    print(f'    {k:20} = {v}')

# Verifica no Hubtrix se chegou
if final[0] == 'concluido':
    print('\n  Lead enviado pro Hubtrix? (verificando ultima execution)')
    r = requests.get(f'{BASE}/api/v1/executions', params={'workflowId': 'Df1BgcXdg3HAUZwf', 'limit': 1},
                     headers={'X-N8N-API-KEY': KEY}, timeout=10)
    eid = r.json().get('data', [])[0]['id']
    r2 = requests.get(f'{BASE}/api/v1/executions/{eid}?includeData=true',
                      headers={'X-N8N-API-KEY': KEY}, timeout=15)
    run = r2.json().get('data', {}).get('resultData', {}).get('runData', {})
    if 'Enviar Lead Hubtrix' in run:
        try:
            out = run['Enviar Lead Hubtrix'][0]['data']['main'][0][0]['json']
            print(f'    Hubtrix retornou: {json.dumps(out, ensure_ascii=False)[:400]}')
        except (KeyError, IndexError, TypeError) as e:
            print(f'    (output indisponivel, mas nodo executou OK: {type(e).__name__})')
    else:
        print('    Nao foi pro Hubtrix nesta ultima execucao')
