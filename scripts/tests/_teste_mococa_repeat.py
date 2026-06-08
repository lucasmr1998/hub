"""Repete o caso Mococa algumas vezes pra ver consistencia de roteamento + givesServiceToCity."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import requests

URL = 'https://automation-n8n.v4riem.easypanel.host/webhook/nuvyion'
for i in range(3):
    payload = {'question': 'Qual o CEP do seu endereço?', 'answer': '13730000',
               'cellphone': '5519999990000'}
    try:
        r = requests.post(URL, json=payload, timeout=90)
        d = r.json()
        keys = list(d.keys())
        gv = d.get('givesServiceToCity', '-')
        print(f'#{i+1} HTTP {r.status_code} keys={keys} givesServiceToCity={gv}')
    except Exception as e:
        print(f'#{i+1} ERRO:', str(e)[:200])
