# -*- coding: utf-8 -*-
"""Teste correcao de PLANO — dispara tudo, valida no fim via exec N8N."""
import time, sys, io, requests, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdout.reconfigure(line_buffering=True)
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
WEBHOOK = BASE + '/webhook/vero-orquestrador'
APIH = {'X-N8N-API-KEY': env['N8N_API_KEY']}
TEL = '5500034222'

def post(txt, img=None):
    body = {'EventType': 'messages',
            'chat': {'wa_chatid': TEL + '@s.whatsapp.net', 'phone': TEL, 'name': 'TestePlano'},
            'message': {'text': txt or '', 'fromMe': False,
                        'messageType': 'ImageMessage' if img else 'Conversation',
                        'mediaType': 'image' if img else ''}}
    if img:
        body['message']['content'] = {'URL': img, 'mimetype': 'image/jpeg'}
    for _ in range(4):
        try:
            return requests.post(WEBHOOK, json=body, timeout=45).status_code
        except Exception:
            time.sleep(3)
    return 'ERR'

RG_F = 'https://i.imgur.com/F0g5wWb.jpeg'
RG_V = 'https://i.imgur.com/W0xAQHC.jpeg'
SEQ = [
    ('oi', None), ('Carla Plano Teste', None), ('17013-000', None), ('sim', None),
    ('300', None), ('bloco 2', None), ('1', None), ('111.444.777-35', None),
    ('05/05/1992', None), ('carla.plano@example.com', None),
    ('', RG_F), ('', RG_V),
    ('nao', None), ('plano', None), ('6', None),
]
for txt, img in SEQ:
    sc = post(txt, img)
    print((txt or '[img]').ljust(26), 'HTTP=' + str(sc), flush=True)
    time.sleep(8)

print('\nAguardando processamento final...', flush=True)
time.sleep(6)

# Busca a exec do '6' e mostra a resposta_bot final
r = requests.get(BASE + '/api/v1/executions?workflowId=Df1BgcXdg3HAUZwf&limit=20', headers=APIH, timeout=20)
for ex in r.json()['data']:
    r2 = requests.get(BASE + '/api/v1/executions/' + str(ex['id']) + '?includeData=true', headers=APIH, timeout=20)
    runs = r2.json().get('data', {}).get('resultData', {}).get('runData', {})
    if 'Entrada' not in runs:
        continue
    en = runs['Entrada'][0]['data']['main'][0][0]['json']
    if en.get('telefone') != TEL or str(en.get('mensagem')) != '6':
        continue
    print('\n=== exec do "6" (correcao de plano) ===', flush=True)
    for nm in ['SmartSkip', 'PegarRespostaBot']:
        if nm in runs:
            o = runs[nm][0].get('data', {}).get('main', [[{}]])
            j = o[0][0].get('json', {}) if o and o[0] else {}
            rb = str(j.get('resposta_bot', '(ausente)'))[:90]
            print('  ' + nm + ' -> proximo_nodo=' + str(j.get('proximo_nodo')), flush=True)
            print('     resposta_bot: ' + repr(rb), flush=True)
    # veredito
    pb = runs.get('PegarRespostaBot', [{}])[0].get('data', {}).get('main', [[{}]])
    rb_final = str((pb[0][0].get('json', {}) if pb and pb[0] else {}).get('resposta_bot', ''))
    ok = 'Confere' in rb_final or 'confirmar' in rb_final.lower() or 'Posso confirmar' in rb_final
    print('\n  RESULTADO: ' + ('PASSOU (voltou pro resumo)' if ok else 'FALHOU (nao mostrou resumo)'), flush=True)
    break
