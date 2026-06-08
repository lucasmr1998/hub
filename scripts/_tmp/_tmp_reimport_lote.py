"""Reimporta conversas TR Carrion com lacuna (so msgs de agente, zero contato).

Telefones identificados na auditoria:
- 308 / 5514991414065
- 278 / 5519953228132
- 273 / 5514998857907
- 250 / 5514998857907
- 258 / 5514996518338
- 249 / 5514998663827
- 248 / 5514991749030
- 244 / 5514996518338

Janela: ultimos 7 dias.
"""
import os, django, requests, time, sys
from datetime import datetime, timezone, timedelta
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.sistema.models import Tenant
from apps.inbox.models import Mensagem, Conversa
from django.core.files.base import ContentFile

APPLY = '--apply' in sys.argv
t = Tenant.objects.get(slug="tr-carrion")
i = IntegracaoAPI.all_tenants.filter(tenant=t, tipo="uazapi", ativa=True).first()
TOKEN = i.api_key or i.access_token or (i.configuracoes_extras or {}).get("token") or ""
H_UAZ = {"token": TOKEN, "Content-Type":"application/json"}
BASE_UAZ = i.base_url.rstrip('/')

HUB_SECRET = os.environ.get('N8N_WEBHOOK_SECRET','')
H_HUB = {"X-N8N-Webhook-Secret": HUB_SECRET, "Content-Type":"application/json"}
HUB_URL = "https://app.hubtrix.com.br/api/public/n8n/inbox/mensagem/"
HUB_DL = "https://app.hubtrix.com.br"

ALVOS = [
    (308, '5514991414065'),
    (278, '5519953228132'),
    (273, '5514998857907'),
    (250, '5514998857907'),
    (258, '5514996518338'),
    (249, '5514998663827'),
    (248, '5514991749030'),
    (244, '5514996518338'),
]

JANELA_DIAS = 2
INI = (datetime.now(timezone.utc) - timedelta(days=JANELA_DIAS)).timestamp() * 1000

total_ok = total_err = 0
for conv_id, tel in ALVOS:
    print(f'\n=== Conversa #{conv_id} tel={tel} ===')
    chatid = tel + '@s.whatsapp.net'
    # Puxa historico
    all_msgs, offset = [], 0
    while True:
        r = requests.post(BASE_UAZ + '/message/find', headers=H_UAZ, json={
            "operator":"AND","sort":"messageTimestamp","limit":200,"offset":offset,
            "filters":[{"field":"chatid","operator":"=","value":chatid}],
        }, timeout=30)
        batch = r.json().get('messages', [])
        if not batch: break
        all_msgs.extend(batch)
        if not r.json().get('hasMore'): break
        offset += len(batch)
        if offset > 1000: break
    janela = [m for m in all_msgs if int(m.get('messageTimestamp', 0)) > INI]
    janela.sort(key=lambda x: int(x.get('messageTimestamp', 0)))

    # Dedupe primario por identificador_externo
    existentes_id = set(Mensagem.all_tenants.filter(
        conversa_id=conv_id,
    ).values_list('identificador_externo', flat=True))
    existentes_id = {e for e in existentes_id if e}
    # Dedupe secundario por (timestamp +- 5s, primeiros 40 chars do conteudo)
    msgs_existentes = list(Mensagem.all_tenants.filter(
        conversa_id=conv_id,
        data_envio__gte=datetime.fromtimestamp(INI/1000, timezone.utc),
    ).values('data_envio', 'conteudo'))
    def ja_existe_aprox(m):
        mid = m.get('id') or m.get('messageid','')
        if mid in existentes_id: return True
        ts = int(m.get('messageTimestamp', 0)) // 1000
        cont = (m.get('content') or {})
        if isinstance(cont, dict):
            txt = (cont.get('text') or cont.get('caption') or cont.get('fileName') or '')[:40]
        else: txt = ''
        for ex in msgs_existentes:
            if abs((ex['data_envio'].timestamp() - ts)) < 5 and (ex['conteudo'] or '')[:40] == txt:
                return True
        return False
    faltantes = [m for m in janela if not ja_existe_aprox(m)]
    print(f'  uazapi: {len(janela)} msgs ultimos {JANELA_DIAS}d | hubtrix: {len(existentes_id)} ids + {len(msgs_existentes)} aprox | faltantes: {len(faltantes)}')
    if not faltantes: continue

    for m in faltantes:
        mid = m.get('id') or m.get('messageid','')
        fm = m.get('fromMe', False)
        tipo = m.get('messageType','')
        cont = m.get('content') or {}
        texto = ''
        if isinstance(cont, dict):
            texto = cont.get('text') or cont.get('caption') or cont.get('fileName') or ''
        is_midia = tipo in ('DocumentMessage','ImageMessage','AudioMessage','VideoMessage','StickerMessage')
        if is_midia and not texto:
            texto = f'[{tipo} — recuperado da uazapi]'
        payload = {
            "tenant_slug":"tr-carrion","telefone":tel,
            "conteudo": texto or '(vazio)',
            "direcao":"enviada" if fm else "recebida",
            "canal_identif":"553181167572","tipo_conteudo":"texto",
            "msg_id_externo": mid,
        }
        if not APPLY:
            total_ok += 1
            continue
        try:
            r = requests.post(HUB_URL, headers=H_HUB, json=payload, timeout=20)
            if r.status_code in (200, 201): total_ok += 1
            else: total_err += 1; print(f'    ERR {r.status_code}: {r.text[:120]}')
        except Exception as e:
            total_err += 1; print(f'    EXC {type(e).__name__}: {e}')
        time.sleep(0.12)

print(f'\n{"APPLY" if APPLY else "DRY-RUN"} TOTAL: ok={total_ok} err={total_err}')
