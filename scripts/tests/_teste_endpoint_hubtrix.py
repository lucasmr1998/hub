"""
Testa o endpoint /api/public/n8n/lead/ do Hubtrix em producao.

1. POST sem header de secret  -> esperado 401
2. POST com header errado     -> esperado 401
3. POST com header correto    -> esperado 201 (cria lead) ou 200 (ja existia)
"""
import json
import requests
from dotenv import dotenv_values

env = dotenv_values('.env.n8n')
HUB = env['HUBTRIX_URL'].rstrip('/')
SECRET = env['HUBTRIX_N8N_WEBHOOK_SECRET']
URL = f'{HUB}/api/public/n8n/lead/'

payload = {
    'tenant_slug': 'tr-carrion',
    'telefone': '5562999000111',
    'nome_razaosocial': 'Teste Diagnostico Vero',
    'email': 'teste-diag@example.com',
    'cep': '74000-000',
    'cidade': 'Goiania',
    'estado': 'GO',
    'plano_interesse': 'Plano 500MB',
    'observacoes': 'Lead simulado via diagnostico do orquestrador N8N',
    'origem': 'whatsapp_n8n',
    'canal_entrada': 'whatsapp',
    'dados_extras': {'origem_teste': 'script_diagnostico'},
}

print(f'URL: {URL}\n')

print('=== 1. SEM header (esperado 401) ===')
r = requests.post(URL, json=payload, timeout=15)
print(f'  status={r.status_code}  body={r.text[:200]}\n')

print('=== 2. Header ERRADO (esperado 401) ===')
r = requests.post(URL, json=payload, headers={'X-N8N-Webhook-Secret': 'errado'}, timeout=15)
print(f'  status={r.status_code}  body={r.text[:200]}\n')

print('=== 3. Header CORRETO (esperado 201/200) ===')
r = requests.post(URL, json=payload, headers={'X-N8N-Webhook-Secret': SECRET}, timeout=15)
print(f'  status={r.status_code}')
try:
    print(f'  body={json.dumps(r.json(), indent=2, ensure_ascii=False)}')
except Exception:
    print(f'  body={r.text[:500]}')

print('\nInterpretacao:')
if r.status_code == 401:
    print('  -> N8N_WEBHOOK_SECRET nao esta setado no container Hubtrix em producao.')
    print('     Adicionar no EasyPanel e dar Restart.')
elif r.status_code == 404:
    print('  -> Tenant tr-carrion nao encontrado.')
elif r.status_code in (200, 201):
    print('  -> Endpoint funcionando ok. Lead criado/atualizado.')
else:
    print(f'  -> Status inesperado {r.status_code}. Conferir logs do container.')
