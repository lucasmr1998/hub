"""Smoke test: bate no /webhook/nuvyion1 com uma pergunta de CEP (Mococa e um fora)
e mostra a resposta (esp. givesServiceToCity). Valida a cadeia de viabilidade no fluxo.
"""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import requests

URL = 'https://automation-n8n.v4riem.easypanel.host/webhook/nuvyion'
casos = [
    ('Mococa centro', '13730000'),
    ('SP capital (fora)', '01310100'),
]
for nome, cep in casos:
    payload = {'question': 'Qual o CEP do seu endereço?', 'answer': cep,
               'cellphone': '5519999990000'}
    print(f'\n=== {nome} (CEP {cep}) ===')
    try:
        r = requests.post(URL, json=payload, timeout=90)
        print('HTTP', r.status_code)
        try:
            print(json.dumps(r.json(), ensure_ascii=False, indent=1)[:1200])
        except Exception:
            print('resp:', r.text[:600])
    except Exception as e:
        print('ERRO:', str(e)[:300])
