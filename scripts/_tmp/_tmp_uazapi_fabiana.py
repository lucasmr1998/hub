import os, django, requests, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.sistema.models import Tenant
t = Tenant.objects.get(slug="tr-carrion")
i = IntegracaoAPI.all_tenants.filter(tenant=t, tipo="uazapi", ativa=True).first()
TOKEN = i.api_key or i.access_token or (i.configuracoes_extras or {}).get("token") or ""
H = {"token": TOKEN, "Content-Type":"application/json"}
BASE = i.base_url.rstrip('/')

TEL = "5514991123891"
CHAT_ID = TEL + "@s.whatsapp.net"

r = requests.post(BASE + "/message/find", headers=H, json={
    "operator": "AND",
    "sort": "messageTimestamp",
    "limit": 200,
    "filters": [{"field": "chatid", "operator": "=", "value": CHAT_ID}],
}, timeout=30)
print(f"status={r.status_code}")
data = r.json()
msgs = data.get("messages", [])
print(f"total mensagens da Fabiana no uazapi: {len(msgs)}  hasMore={data.get('hasMore')}")
print(f"\nTimeline (todas as msgs):")
print(f"{'ts':<12} {'fromMe':<6} {'type':<14} {'msgid':<24} preview")
for m in msgs:
    ts = m.get('messageTimestamp')
    from datetime import datetime
    try:
        ts_int = int(ts)
        if ts_int > 1e12: ts_int //= 1000  # ms -> s
        hora = datetime.fromtimestamp(ts_int).strftime('%d/%m %H:%M:%S')
    except Exception:
        hora = '?'
    fm = m.get('fromMe', False)
    tipo = m.get('messageType','?')
    mid = (m.get('id') or m.get('messageid') or '')[:23]
    txt = ''
    cont = m.get('content') or {}
    if isinstance(cont, dict):
        txt = cont.get('text') or cont.get('caption') or cont.get('fileName') or '(midia sem texto)'
    print(f"  {hora:<12} {str(fm):<6} {tipo:<14} {mid:<24} {str(txt)[:70]}")
