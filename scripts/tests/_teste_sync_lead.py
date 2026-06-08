"""
Teste rapido: bot recebe oi -> pede nome -> cliente manda nome.
Valida que o Hubtrix Lead foi atualizado a cada turno com dados_lead.
"""
import time, sys, io, json, requests, psycopg2
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdout.reconfigure(line_buffering=True)
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
env_prod = dotenv_values('.env.prod_readonly')
WEBHOOK = f"{env['N8N_BASE_URL'].rstrip('/')}/webhook/vero-orquestrador"
TEL = '5500066001'

def post(txt):
    body = {
        'EventType':'messages',
        'chat':{'wa_chatid':f'{TEL}@s.whatsapp.net','phone':TEL,'name':'TestSync'},
        'message':{'text':txt,'fromMe':False,'messageType':'Conversation','mediaType':''}
    }
    r = requests.post(WEBHOOK, json=body, timeout=20)
    return r.status_code

def db_lead():
    c = psycopg2.connect(host=env_prod['PROD_DB_HOST'], port=int(env_prod['PROD_DB_PORT']),
        database=env_prod['PROD_DB_NAME'], user=env_prod['PROD_DB_USER'],
        password=env_prod['PROD_DB_PASSWORD'], connect_timeout=10)
    cur = c.cursor()
    cur.execute("""SELECT l.id, l.nome_razaosocial, l.email, l.cep, l.cpf_cnpj,
                          l.cidade, l.estado, l.numero_residencia, l.data_nascimento
                     FROM leads_prospectos l
                    WHERE l.tenant_id=11 AND l.telefone=%s
                    ORDER BY l.id DESC LIMIT 1;""", (TEL,))
    r = cur.fetchone(); cur.close(); c.close()
    return r

def db_session():
    c = psycopg2.connect(host='103.199.187.4', port=5434, database='banco_n8n',
        user='admin', password='Gremio271293@')
    cur = c.cursor()
    cur.execute("SELECT nodo_atual, dados FROM vero_session WHERE telefone=%s;", (TEL,))
    r = cur.fetchone(); cur.close(); c.close()
    return r

def step(label, msg, pause=5):
    print(f'\n>>> {label}: {msg!r}')
    sc = post(msg); time.sleep(pause)
    s = db_session(); l = db_lead()
    print(f'  HTTP={sc}')
    if s: print(f'  session: nodo={s[0]} dados={json.dumps(s[1], ensure_ascii=False)[:120]}')
    if l: print(f'  LEAD #{l[0]}: nome={l[1]!r} email={l[2]!r} cep={l[3]!r} cpf={l[4]!r} numero={l[7]!r}')

step('1. saudacao', 'oi')
step('2. nome', 'Joao da Silva Tester')
step('3. plano', 'quero 500 mega')
step('4. cep', '17013-000', pause=6)
step('5. confirmar', 'sim')
step('6. numero', '100')

print('\n=== FIM ===')
