"""Reimporta msgs perdidas da Fabiana (01/06) puxando do uazapi e mandando
pro endpoint /api/public/n8n/inbox/mensagem/ do Hubtrix.

PRECONDICAO: rebuild com hotfix 2396dce ja aplicado (numero_residencia max 100).
"""
import os, django, requests, time
from datetime import datetime, timezone
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.sistema.models import Tenant
from apps.inbox.models import Mensagem

t = Tenant.objects.get(slug="tr-carrion")
i = IntegracaoAPI.all_tenants.filter(tenant=t, tipo="uazapi", ativa=True).first()
TOKEN = i.api_key or i.access_token or (i.configuracoes_extras or {}).get("token") or ""
H_UAZ = {"token": TOKEN, "Content-Type":"application/json"}
BASE_UAZ = i.base_url.rstrip('/')

import os as _os
HUB_SECRET = _os.environ.get('N8N_WEBHOOK_SECRET','')
H_HUB = {"X-N8N-Webhook-Secret": HUB_SECRET, "Content-Type":"application/json"}
HUB_URL = "https://app.hubtrix.com.br/api/public/n8n/inbox/mensagem/"

TEL = "5514991123891"
CHAT_ID = TEL + "@s.whatsapp.net"

# Puxa todas as msgs hoje
all_msgs, offset = [], 0
while True:
    r = requests.post(BASE_UAZ + "/message/find", headers=H_UAZ, json={
        "operator":"AND","sort":"messageTimestamp","limit":200,"offset":offset,
        "filters":[{"field":"chatid","operator":"=","value":CHAT_ID}],
    }, timeout=30)
    batch = r.json().get("messages", [])
    if not batch: break
    all_msgs.extend(batch)
    if not r.json().get("hasMore"): break
    offset += len(batch)
    if offset > 1000: break

HOJE_INI = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
hoje = [m for m in all_msgs if int(m.get('messageTimestamp', 0)) > HOJE_INI]
existentes = set(Mensagem.all_tenants.filter(conversa_id=317).values_list('identificador_externo', flat=True))
existentes = {e for e in existentes if e}

faltantes = [m for m in hoje if (m.get('id') or m.get('messageid','')) not in existentes]
faltantes.sort(key=lambda x: int(x.get('messageTimestamp', 0)))
print(f"Total hoje no uazapi: {len(hoje)}  ja em Hubtrix: {len(existentes)}  faltantes: {len(faltantes)}")

# DRY RUN por padrao — passar --apply pra rodar
import sys
APPLY = '--apply' in sys.argv

ok, err, skip_media = 0, 0, 0
for m in faltantes:
    mid = m.get('id') or m.get('messageid','')
    fm = m.get('fromMe', False)
    tipo = m.get('messageType','')
    cont = m.get('content') or {}
    ts_ms = int(m.get('messageTimestamp', 0))
    hora = datetime.fromtimestamp(ts_ms//1000, timezone.utc).astimezone().strftime('%H:%M:%S')

    # Texto
    texto = ''
    if isinstance(cont, dict):
        texto = cont.get('text') or cont.get('caption') or cont.get('fileName') or ''

    # Skip mídia por agora — vamos reimportar texto primeiro, mídia em segundo passo
    is_midia = tipo in ('DocumentMessage','ImageMessage','AudioMessage','VideoMessage','StickerMessage')
    if is_midia and not texto:
        texto = f'[{tipo} — recuperado da uazapi: {(cont.get("fileName") or "mídia")}]'

    payload = {
        "tenant_slug": "tr-carrion",
        "telefone": TEL,
        "conteudo": texto or '(vazio)',
        "direcao": "enviada" if fm else "recebida",
        "canal_identif": "553181167572",
        "tipo_conteudo": "texto",
        "msg_id_externo": mid,
        "nome_contato": "Fabiana",
    }

    if not APPLY:
        print(f"  [DRY] {hora} {('AGENTE' if fm else 'CONTATO'):<8} {tipo[:18]:<18} {(texto or '')[:55]}")
        ok += 1
        continue

    try:
        r = requests.post(HUB_URL, headers=H_HUB, json=payload, timeout=20)
        if r.status_code in (200, 201):
            ok += 1
            print(f"  [OK]  {hora} {('AG' if fm else 'CT'):<3} {(texto or '')[:65]}")
        else:
            err += 1
            print(f"  [ERR {r.status_code}] {hora} {(texto or '')[:60]} :: {r.text[:120]}")
    except Exception as e:
        err += 1
        print(f"  [EXC] {hora} {type(e).__name__}: {e}")
    time.sleep(0.15)  # respira pra nao apavorar o server

print(f"\n{'APPLY' if APPLY else 'DRY-RUN'}: ok={ok} err={err} skip_media={skip_media}")
