"""Limpa msg smoke + baixa midias do uazapi e anexa as msgs reimportadas (conv 317)."""
import os, django, requests, json
from datetime import datetime, timezone
os.environ.setdefault("DJANGO_SETTINGS_MODULE","gerenciador_vendas.settings")
django.setup()
from apps.integracoes.models import IntegracaoAPI
from apps.sistema.models import Tenant
from apps.inbox.models import Mensagem
from django.core.files.base import ContentFile

t = Tenant.objects.get(slug="tr-carrion")
i = IntegracaoAPI.all_tenants.filter(tenant=t, tipo="uazapi", ativa=True).first()
TOKEN = i.api_key or i.access_token or (i.configuracoes_extras or {}).get("token") or ""
H = {"token": TOKEN, "Content-Type":"application/json"}
BASE = i.base_url.rstrip('/')

# 1) Limpa smoke msgs
qs = Mensagem.all_tenants.filter(conteudo__icontains='_smoke_pos_rebuild_ignorar_')
print(f'Apagando {qs.count()} msgs smoke...')
for m in qs:
    print(f'  delete msg#{m.pk} conv#{m.conversa_id} conteudo={m.conteudo[:60]!r}')
    m.delete()

# 2) Lista todas msgs reimportadas hoje com referencia a midia
TEL = "5514991123891"
CHAT_ID = TEL + "@s.whatsapp.net"

all_msgs, offset = [], 0
while True:
    r = requests.post(BASE + "/message/find", headers=H, json={
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
midias = [m for m in hoje if m.get('messageType') in ('DocumentMessage','ImageMessage','AudioMessage','VideoMessage','StickerMessage')]
print(f'\nMidias hoje no uazapi: {len(midias)}')

# 3) Pra cada midia, tenta endpoints de download uazapi
ENDPOINTS_DL = [
    '/message/download',
    '/chat/getMedia',
    '/media/download',
]

for m in midias:
    mid = m.get('id') or m.get('messageid','')
    tipo = m.get('messageType')
    cont = m.get('content') or {}
    fname = cont.get('fileName') or f'{mid}.bin'
    ts_ms = int(m.get('messageTimestamp', 0))
    hora = datetime.fromtimestamp(ts_ms//1000, timezone.utc).astimezone().strftime('%H:%M:%S')
    print(f'\n--- {hora} {tipo} id={mid[:25]} fileName={fname!r} ---')

    # Encontra msg correspondente no Hubtrix
    msg_hub = Mensagem.all_tenants.filter(conversa_id=317, identificador_externo=mid).first()
    if not msg_hub:
        print(f'  (msg nao reimportada, skip)')
        continue
    print(f'  msg_hub#{msg_hub.pk} tipo_atual={msg_hub.tipo_conteudo!r}')

    # Tenta endpoints uazapi pra download
    data = None
    for ep in ENDPOINTS_DL:
        try:
            r = requests.post(BASE + ep, headers=H, json={'id': mid}, timeout=60)
            if r.status_code == 200:
                ct = r.headers.get('Content-Type','')
                if 'json' in ct:
                    j = r.json()
                    print(f'  [{ep}] 200 json keys={list(j.keys())[:6]}')
                    # uazapi geralmente retorna {url, base64, mimetype, ...}
                    url = j.get('fileURL') or j.get('url') or j.get('mediaUrl')
                    b64 = j.get('base64') or j.get('data')
                    mime = j.get('mimetype') or j.get('mimeType')
                    if url:
                        rb = requests.get(url, timeout=60)
                        if rb.ok:
                            data = (rb.content, mime or 'application/octet-stream')
                            print(f'    baixou {len(data[0])} bytes via URL ({mime})')
                            break
                    elif b64:
                        import base64 as _b
                        data = (_b.b64decode(b64), mime or 'application/octet-stream')
                        print(f'    decoded base64 {len(data[0])} bytes ({mime})')
                        break
                else:
                    data = (r.content, ct or 'application/octet-stream')
                    print(f'    baixou {len(r.content)} bytes ({ct}) direto')
                    break
            else:
                print(f'  [{ep}] {r.status_code} {r.text[:120]!r}')
        except Exception as e:
            print(f'  [{ep}] EXC {type(e).__name__}: {e}')

    if not data:
        print(f'  ❌ Nao conseguiu baixar — endpoints disponiveis nao funcionaram')
        continue

    # Salva no FileField
    conteudo_bytes, mime = data
    map_tipo = {
        'DocumentMessage': 'arquivo', 'ImageMessage': 'imagem',
        'AudioMessage': 'audio', 'VideoMessage': 'video',
        'StickerMessage': 'imagem',
    }
    msg_hub.tipo_conteudo = map_tipo.get(tipo, 'arquivo')
    msg_hub.arquivo.save(fname, ContentFile(conteudo_bytes), save=False)
    msg_hub.arquivo_nome = fname
    msg_hub.arquivo_tamanho = len(conteudo_bytes)
    msg_hub.save(update_fields=['tipo_conteudo','arquivo','arquivo_nome','arquivo_tamanho'])
    print(f'  ✓ anexado em msg#{msg_hub.pk} tipo={msg_hub.tipo_conteudo}')
