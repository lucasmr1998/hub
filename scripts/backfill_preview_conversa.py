"""
Backfill: popula ultima_mensagem_preview/em em conversas onde
ficou vazio mas ja existe Mensagem. Idempotente, read-mostly.

Uso (em prod, dentro do container):
  python manage.py shell < scripts/backfill_preview_conversa.py
"""
from apps.inbox.models import Conversa, Mensagem
from apps.inbox.services import preview_mensagem

qs = Conversa.all_tenants.filter(ultima_mensagem_preview='')
total = qs.count()
print(f'Conversas com preview vazio: {total}')

atualizadas = 0
for conv in qs.iterator(chunk_size=200):
    ultima = (
        Mensagem.all_tenants
        .filter(tenant_id=conv.tenant_id, conversa=conv)
        .order_by('-data_envio')
        .first()
    )
    if not ultima:
        continue
    preview = preview_mensagem(ultima.conteudo, ultima.tipo_conteudo)
    if not preview:
        continue
    conv.ultima_mensagem_em = ultima.data_envio
    conv.ultima_mensagem_preview = preview
    conv.save(update_fields=['ultima_mensagem_em', 'ultima_mensagem_preview'])
    atualizadas += 1

print(f'Atualizadas: {atualizadas} / {total}')
