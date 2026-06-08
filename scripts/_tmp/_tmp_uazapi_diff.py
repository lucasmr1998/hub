"""Lista msgs Fabiana hoje no uazapi e marca quais NÃO estão no Hubtrix."""
import os, django, requests
from datetime import datetime, timezone
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.sistema.models import Tenant
from apps.inbox.models import Mensagem

t = Tenant.objects.get(slug="tr-carrion")
i = IntegracaoAPI.all_tenants.filter(tenant=t, tipo="uazapi", ativa=True).first()
TOKEN = i.api_key or i.access_token or (i.configuracoes_extras or {}).get("token") or ""
H = {"token": TOKEN, "Content-Type":"application/json"}
BASE = i.base_url.rstrip('/')

TEL = "5514991123891"
CHAT_ID = TEL + "@s.whatsapp.net"

# Pega todas
all_msgs = []
offset = 0
while True:
    r = requests.post(BASE + "/message/find", headers=H, json={
        "operator": "AND", "sort": "messageTimestamp", "limit": 200, "offset": offset,
        "filters": [{"field": "chatid", "operator": "=", "value": CHAT_ID}],
    }, timeout=30)
    data = r.json()
    batch = data.get("messages", [])
    if not batch: break
    all_msgs.extend(batch)
    if not data.get("hasMore"): break
    offset += len(batch)
    if offset > 1000: break
print(f"Total msgs no uazapi: {len(all_msgs)}")

# Filtra HOJE (01/06 UTC)
HOJE_INI = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
hoje = [m for m in all_msgs if int(m.get('messageTimestamp', 0)) > HOJE_INI]
print(f"Msgs hoje 01/06: {len(hoje)}")

# wa_msg_ids ja registrados no Hubtrix conv 317
existentes = set(Mensagem.all_tenants.filter(conversa_id=317).values_list('identificador_externo', flat=True))
existentes = {e for e in existentes if e}
print(f"wa_msg_ids ja em inbox_mensagens conv 317: {len(existentes)}")

print(f"\n=== Msgs no uazapi HOJE x Hubtrix ===")
print(f"{'hora':<10} {'fromMe':<6} {'type':<22} {'no_hub':<7} {'id':<28} preview")
faltantes = []
for m in sorted(hoje, key=lambda x: int(x.get('messageTimestamp', 0))):
    ts = int(m['messageTimestamp']) // 1000
    hora = datetime.fromtimestamp(ts, timezone.utc).astimezone().strftime('%H:%M:%S')
    mid = m.get('id') or m.get('messageid') or ''
    fm = m.get('fromMe', False)
    tipo = m.get('messageType','?')
    cont = m.get('content') or {}
    txt = ''
    if isinstance(cont, dict):
        txt = cont.get('text') or cont.get('caption') or cont.get('fileName') or '(midia)'
    no_hub = '✓' if mid in existentes else '❌'
    print(f"  {hora:<10} {str(fm):<6} {tipo:<22} {no_hub:<7} {mid[:27]:<28} {str(txt)[:65]}")
    if mid not in existentes:
        faltantes.append(m)

print(f"\n>>> FALTANTES: {len(faltantes)} msgs precisam ser re-importadas")
