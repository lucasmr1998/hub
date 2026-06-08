"""
Teste E2E: roda conversa do bot do inicio ao fim usando um telefone novo
e move a oportunidade para 'Cliente Ativo' (estagio ganho).

NAO destrutivo em escala global: cria 1 lead/op/conv no tenant tr-carrion
com telefone de teste e move a oportunidade desse mesmo registro.
"""
import json
import sys
import io
import time
import requests
import psycopg2
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdout.reconfigure(line_buffering=True)

env_n8n = dotenv_values('.env.n8n')
env_prod = dotenv_values('.env.prod_readonly')
WEBHOOK = f"{env_n8n['N8N_BASE_URL'].rstrip('/')}/webhook/vero-orquestrador"
TEL = '5500077555'  # telefone novo de teste (limpo)
ESTAGIO_GANHO_ID = 55  # Cliente Ativo

def db():
    return psycopg2.connect(
        host=env_prod['PROD_DB_HOST'], port=int(env_prod['PROD_DB_PORT']),
        database=env_prod['PROD_DB_NAME'], user=env_prod['PROD_DB_USER'],
        password=env_prod['PROD_DB_PASSWORD'], connect_timeout=10,
    )

def post(tel, txt, img_url=None):
    body = {
        'EventType': 'messages',
        'chat': {'wa_chatid': f'{tel}@s.whatsapp.net', 'phone': tel, 'name': f'TesteE2E'},
        'message': {
            'text': txt or '',
            'fromMe': False,
            'messageType': 'ImageMessage' if img_url else 'Conversation',
            'mediaType': 'image' if img_url else '',
        }
    }
    if img_url:
        body['message']['content'] = {'URL': img_url, 'mimetype': 'image/jpeg'}
    r = requests.post(WEBHOOK, json=body, timeout=20)
    return r.status_code

def estado():
    conn = db(); cur = conn.cursor()
    cur.execute("""SELECT c.id, c.modo_atendimento, c.status, c.agente_id, c.equipe_id, c.fila_id,
                          c.lead_id, c.oportunidade_id, l.nome_razaosocial, l.email, l.cep, l.cpf_cnpj,
                          o.estagio_id, o.dados_custom, e.nome
                     FROM inbox_conversas c
                     LEFT JOIN leads_prospectos l ON l.id=c.lead_id
                     LEFT JOIN crm_oportunidades o ON o.id=c.oportunidade_id
                     LEFT JOIN crm_pipeline_estagios e ON e.id=o.estagio_id
                    WHERE c.tenant_id=11 AND c.contato_telefone=%s
                    ORDER BY c.id DESC LIMIT 1;""", (TEL,))
    r = cur.fetchone(); cur.close(); conn.close()
    return r

def msgs():
    conn = db(); cur = conn.cursor()
    cur.execute("""SELECT id, remetente_tipo, conteudo FROM inbox_mensagens
                    WHERE conversa_id IN (
                       SELECT id FROM inbox_conversas WHERE tenant_id=11 AND contato_telefone=%s
                    )
                    ORDER BY id;""", (TEL,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def step(label, msg, *, img=None, pause=5):
    print(f'\n>>> {label}')
    print(f'    USER -> {msg if not img else "[imagem]"}')
    sc = post(TEL, msg, img_url=img)
    print(f'    HTTP={sc}')
    time.sleep(pause)
    e = estado()
    if e:
        print(f'    estado: nodo={e[13].get("nodo_atual") if isinstance(e[13], dict) else "?"} '
              f'modo={e[1]} estagio={e[14]}')

# --- fluxo ---
print(f'\n{"="*70}\n  TESTE E2E — bot Vero TR Carrion\n  Telefone: {TEL}\n{"="*70}')

step('1. Saudacao',                'oi')
step('2. Nome',                    'Lucas Teste E2E')
step('3. Intent plano',            'quero um plano de 500 mega')
step('4. CEP',                     '17013-000')   # Bauru/SP — cobertura tr-carrion
step('5. Confirmar endereco',      'sim')         # bot pede confirmacao
step('6. Numero',                  '1500')
step('7. Complemento',             'apto 42')
step('8. Escolher plano',          '1')           # bot mostra catalogo, escolhe 1
step('9. RG frente',               '',  img='https://i.imgur.com/F0g5wWb.jpeg')
step('10. RG verso',               '',  img='https://i.imgur.com/W0xAQHC.jpeg')
step('11. CPF',                    '111.444.777-35')
step('12. Email',                  'lucasteste.e2e@example.com')
step('13. Data nascimento',        '15/05/1995')
step('14. Confirmacao final',      'sim', pause=6)

# Aguarda processamento final
time.sleep(2)
print('\n--- ESTADO FINAL DO BOT ---')
e = estado()
if not e:
    print('NENHUMA CONVERSA — fluxo nao executou.')
    sys.exit(1)
print(f'  conversa_id={e[0]} modo={e[1]} status={e[2]} agente={e[3]} equipe={e[4]} fila={e[5]}')
print(f'  lead_id={e[6]} nome={e[8]} email={e[9]} cep={e[10]} cpf={e[11]}')
print(f'  op_id={e[7]} estagio={e[14]} dados_custom={json.dumps(e[13], ensure_ascii=False)[:300] if e[13] else "{}"}')

ms = msgs()
print(f'\n--- {len(ms)} mensagens registradas ---')
for m in ms[-12:]:
    print(f'  msg={m[0]} tipo={m[1]:<8} | {(m[2] or "")[:80]}')

# Bot concluiu o atendimento. A movimentacao pra estagio ganho (Cliente Ativo)
# eh acao manual do vendedor no CRM:
#   https://app.hubtrix.com.br/crm/oportunidades/{op_id}/
print(f'\n=== PROXIMO PASSO MANUAL ===')
if not e[7]:
    print('Sem oportunidade — bot nao concluiu cadastro.')
    sys.exit(2)
print(f'  Vendedor abre https://app.hubtrix.com.br/crm/oportunidades/{e[7]}/')
print(f'  E muda estagio para "Cliente Ativo" (id={ESTAGIO_GANHO_ID}).')
