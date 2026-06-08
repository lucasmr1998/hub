"""Procura msg especifica do bot pra Michele e deleta via uazapi."""
import os, django, requests
from datetime import datetime, timezone
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.sistema.models import Tenant

t = Tenant.objects.get(slug="tr-carrion")
i = IntegracaoAPI.all_tenants.filter(tenant=t, tipo="uazapi", ativa=True).first()
TOKEN = i.api_key or i.access_token or (i.configuracoes_extras or {}).get("token") or ""
H = {"token": TOKEN, "Content-Type":"application/json"}
BASE = i.base_url.rstrip('/')

TEL = "55119535515900"  # Michele (13 digitos)
CHAT_ID = TEL + "@s.whatsapp.net"

# Filtra so por chatid (todos os tipos)
r = requests.post(BASE + "/message/find", headers=H, json={
    "operator":"AND","sort":"-messageTimestamp","limit":100,
    "filters":[
        {"field":"chatid","operator":"=","value":CHAT_ID},
        {"field":"fromMe","operator":"=","value":True},
    ],
}, timeout=30)
data = r.json()
msgs = data.get('messages', [])
print(f'Msgs encontradas (filtro chatid+ExtendedText): {len(msgs)}')

candidatas = []
print('Lista das 30 msgs mais recentes (filtro chatid+fromMe):')
for m in msgs[:30]:
    ts = int(m.get('messageTimestamp', 0))
    cont = m.get('content') or {}
    txt = cont.get('text','') if isinstance(cont, dict) else ''
    cid_msg = m.get('chatid','')
    hora = datetime.fromtimestamp(ts//1000, timezone.utc).astimezone().strftime('%H:%M:%S')
    mid = m.get('id') or m.get('messageid','')
    print(f'  {hora} chat={cid_msg[:30]} id={mid[:30]} txt={txt[:50]!r}')
    if 'Vi que voce' in txt:
        candidatas.append({'id': mid, 'hora': hora, 'chatid': cid_msg, 'texto': txt[:60]})

print(f'\nMsgs follow-up enviadas pra Michele: {len(candidatas)}')
for c in candidatas:
    print(f"  {c['hora']} id={c['id']} chat={c['chatid']}")
    print(f"     {c['texto']}")

# Testa endpoints delete pra primeira
if candidatas:
    test_id = candidatas[0]['id']
    print(f'\n=== Testa DELETE pra id={test_id} ===')
    for ep, payload in [
        ('/message/delete', {'id': test_id, 'messageid': test_id}),
        ('/chat/deleteMessage', {'id': test_id, 'fromAll': True, 'remotejid': CHAT_ID}),
        ('/message/revoke', {'id': test_id, 'phone': TEL}),
        ('/chat/deletemessage', {'number': TEL, 'messageid': test_id}),
    ]:
        try:
            r = requests.post(BASE + ep, headers=H, json=payload, timeout=20)
            print(f'  POST {ep}: status={r.status_code} body={r.text[:200]}')
        except Exception as e:
            print(f'  POST {ep}: {type(e).__name__}: {e}')
