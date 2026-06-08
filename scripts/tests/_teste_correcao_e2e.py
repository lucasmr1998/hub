"""Teste E2E do fluxo de correcao (campo complemento)."""
import time, sys, io, requests, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdout.reconfigure(line_buffering=True)
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
WEBHOOK = env['N8N_BASE_URL'].rstrip('/') + '/webhook/vero-orquestrador'
TEL = '5500033888'

def post(txt, img=None):
    body = {'EventType': 'messages',
            'chat': {'wa_chatid': TEL + '@s.whatsapp.net', 'phone': TEL, 'name': 'TesteCorrecao'},
            'message': {'text': txt or '', 'fromMe': False,
                        'messageType': 'ImageMessage' if img else 'Conversation',
                        'mediaType': 'image' if img else ''}}
    if img:
        body['message']['content'] = {'URL': img, 'mimetype': 'image/jpeg'}
    try:
        return requests.post(WEBHOOK, json=body, timeout=30).status_code
    except Exception as e:
        return 'ERR ' + type(e).__name__

def sess():
    c = psycopg2.connect(host='103.199.187.4', port=5434, database='banco_n8n',
                         user='admin', password='Gremio271293@', connect_timeout=10)
    cur = c.cursor()
    cur.execute("SELECT nodo_atual, dados FROM vero_session WHERE telefone=%s;", (TEL,))
    r = cur.fetchone()
    cur.close(); c.close()
    return r if r else ('(sem)', {})

def step(label, msg, img=None, pause=7):
    sc = post(msg, img)
    time.sleep(pause)
    nodo, dados = sess()
    envia = msg if not img else '[imagem]'
    print(label.ljust(24), 'envia=' + repr(envia).ljust(28), 'HTTP=' + str(sc), '-> nodo=' + str(nodo), flush=True)
    return nodo, dados

RG_F = 'https://i.imgur.com/F0g5wWb.jpeg'
RG_V = 'https://i.imgur.com/W0xAQHC.jpeg'

print('=== TESTE CORRECAO E2E -- ' + TEL + ' ===\n', flush=True)
step('1 saudacao',      'oi')
step('2 nome',          'Mariana Teste Correcao')
step('3 cep',           '17013-000', pause=9)
step('4 confirma cep',  'sim')
step('5 numero',        '250')
step('6 complemento',   'casa A')
step('7 escolhe plano', '1')
step('8 cpf',           '111.444.777-35')
step('9 data nasc',     '10/10/1990')
step('10 email',        'mariana.teste@example.com')
step('11 rg frente',    '', img=RG_F)
nodo, dados = step('12 rg verso', '', img=RG_V, pause=9)
print('  >> Apos RG verso: nodo=' + str(nodo) + ' complemento=' + repr(dados.get('complemento')), flush=True)

print('\n--- CORRECAO ---', flush=True)
step('13 recusa resumo', 'nao')
step('14 pede corrigir', 'complemento')
nodo, dados = step('15 novo complemento', 'apartamento 502', pause=9)
print('  >> apos reenvio: nodo=' + str(nodo) + ' complemento=' + repr(dados.get('complemento')), flush=True)
nodo, dados = step('16 confirma final', 'sim', pause=9)

print('\n=== RESULTADO ===', flush=True)
print('  nodo final=' + str(nodo), flush=True)
print('  complemento final=' + repr(dados.get('complemento')) + '  (esperado: apartamento 502)', flush=True)
ok = dados.get('complemento') == 'apartamento 502' and nodo in ('concluido', 'aguarda_decisao_pos_concluido')
print('  ' + ('PASSOU' if ok else 'FALHOU'), flush=True)
