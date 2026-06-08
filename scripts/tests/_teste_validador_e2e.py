"""Teste end-to-end do validador Nuvyon ao vivo (/webhook/nuvyion).
Cenarios: atende (Mococa), nao atende (SP capital), CEP invalido.
Mostra o que o Matrix receberia."""
import sys, json
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import requests

URL = 'https://automation-n8n.v4riem.easypanel.host/webhook/nuvyion'
casos = [
    ('Mococa/SP (deve ATENDER)', '13730150'),
    ('SP capital (NAO atende)', '01310100'),
    ('CEP invalido', '99999999'),
]
for nome, cep in casos:
    payload = {'question': 'Qual o CEP do seu endereço?', 'answer': cep,
               'cellphone': '5519999990000'}
    print(f'\n=== {nome}  (CEP {cep}) ===')
    try:
        r = requests.post(URL, json=payload, timeout=90)
        try:
            d = r.json()
        except Exception:
            print('HTTP', r.status_code, 'resp:', r.text[:300]); continue
        # destaca os campos-chave de decisao
        chave = {k: d.get(k) for k in ('answerIsCorrect', 'givesServiceToCity',
                 'errorMessage', 'localidade', 'uf') if k in d}
        print('HTTP', r.status_code, '| decisao:', json.dumps(chave, ensure_ascii=False))
    except Exception as e:
        print('ERRO:', str(e)[:250])
