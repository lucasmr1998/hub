"""
Webhook dispatcher genérico — Roteia webhooks para o provider correto.

URL: /inbox/api/webhook/<provedor>/<canal_id>/

Cada provider registrado sabe parsear seu próprio payload.
O dispatcher só orquestra: busca o canal, instancia o provider, parseia e salva.
"""
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import CanalInbox
from . import services

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def provider_webhook(request, provedor, canal_id):
    """
    Webhook genérico que roteia para o provider correto.

    URL: /inbox/api/webhook/{provedor}/{canal_id}/

    Configura no painel do provider:
        Uazapi: https://dominio.com/inbox/api/webhook/uazapi/1/
        Evolution: https://dominio.com/inbox/api/webhook/evolution/2/
    """
    # Buscar canal
    try:
        canal = CanalInbox.all_tenants.select_related('integracao').get(
            pk=canal_id, provedor=provedor, ativo=True,
        )
    except CanalInbox.DoesNotExist:
        logger.warning("[Webhook] Canal não encontrado: provedor=%s canal_id=%s", provedor, canal_id)
        return JsonResponse({'error': 'Canal não encontrado'}, status=404)

    # Validar webhook token (opcional, configurável)
    expected_token = (canal.configuracao or {}).get('webhook_token', '')
    if expected_token:
        received_token = request.headers.get('token', request.GET.get('token', ''))
        if received_token != expected_token:
            return JsonResponse({'error': 'Token inválido'}, status=401)

    # Parsear body
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    # Instanciar provider e parsear
    from apps.inbox.providers import get_provider
    try:
        provider = get_provider(canal)
    except ValueError as e:
        logger.error("[Webhook] Erro ao instanciar provider: %s", e)
        return JsonResponse({'error': str(e)}, status=400)

    parsed = provider.parse_webhook(body)

    if parsed is None:
        return JsonResponse({'ok': True, 'ignored': True})

    # Status update (entregue, lido)
    if parsed.get('is_status_update'):
        _processar_status(parsed.get('status_data', {}), canal.tenant)
        return JsonResponse({'ok': True, 'processed': 'status_update'})

    # Mensagem nova → usar service existente
    conversa, mensagem, nova = services.receber_mensagem(
        telefone=parsed['telefone'],
        nome=parsed.get('nome', ''),
        conteudo=parsed.get('conteudo', ''),
        tenant=canal.tenant,
        tipo_conteudo=parsed.get('tipo_conteudo', 'texto'),
        identificador_externo=parsed.get('identificador_externo', ''),
        metadata=parsed.get('metadata', {}),
        canal_tipo=canal.tipo,
        arquivo_url=parsed.get('arquivo_url', ''),
        arquivo_nome=parsed.get('arquivo_nome', ''),
        canal=canal,
    )

    logger.info(
        "[Webhook:%s] Mensagem recebida: conversa=#%s telefone=%s nova=%s",
        provedor, conversa.numero, parsed['telefone'], nova,
    )

    return JsonResponse({
        'ok': True,
        'nova_conversa': nova,
        'conversa_id': conversa.pk,
        'mensagem_id': mensagem.pk,
    }, status=201)


def _processar_status(data, tenant):
    """Processa evento de status de mensagem."""
    updates = data if isinstance(data, list) else [data]
    for update in updates:
        key = update.get('key', {})
        msg_id = key.get('id', '')
        status_update = update.get('update', {})
        status_val = status_update.get('status')
        if msg_id and status_val:
            status_map = {2: 'enviado', 3: 'entregue', 4: 'lido'}
            status_str = status_map.get(status_val, str(status_val))
            services.atualizar_status_entrega(
                identificador_externo=msg_id,
                status_entrega=status_str,
                tenant=tenant,
            )
