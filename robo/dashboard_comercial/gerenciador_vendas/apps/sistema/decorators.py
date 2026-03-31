import functools
import logging
import os

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)


def webhook_token_required(view_func):
    """Valida token secreto no header Authorization para webhooks.

    Espera: Authorization: Bearer <WEBHOOK_SECRET_TOKEN>
    Retorna 401 se ausente ou inválido.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        expected_token = os.environ.get('WEBHOOK_SECRET_TOKEN', '')
        if not expected_token:
            logger.error("[SEGURANÇA] WEBHOOK_SECRET_TOKEN não definido no ambiente.")
            return JsonResponse({'error': 'Webhook não configurado'}, status=503)

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            logger.warning("[SEGURANÇA] Webhook sem token: %s %s", request.method, request.path)
            return JsonResponse({'error': 'Token obrigatório'}, status=401)

        token = auth_header[7:]
        if token != expected_token:
            logger.warning("[SEGURANÇA] Webhook com token inválido: %s %s", request.method, request.path)
            return JsonResponse({'error': 'Token inválido'}, status=401)

        return view_func(request, *args, **kwargs)
    return wrapper


def api_token_required(view_func):
    """Valida token de API no header Authorization para integrações externas (N8N).

    Espera: Authorization: Bearer <N8N_API_TOKEN>
    Retorna 401 se ausente ou inválido.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        expected_token = os.environ.get('N8N_API_TOKEN', '')
        if not expected_token:
            logger.error("[SEGURANÇA] N8N_API_TOKEN não definido no ambiente.")
            return JsonResponse({'error': 'API não configurada'}, status=503)

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            logger.warning("[SEGURANÇA] API sem token: %s %s", request.method, request.path)
            return JsonResponse({'error': 'Token obrigatório'}, status=401)

        token = auth_header[7:]
        if token != expected_token:
            logger.warning("[SEGURANÇA] API com token inválido: %s %s", request.method, request.path)
            return JsonResponse({'error': 'Token inválido'}, status=401)

        return view_func(request, *args, **kwargs)
    return wrapper


def get_tenant_object_or_404(model, request, **kwargs):
    """Get object filtered by current tenant. Raises 404 if not found or wrong tenant."""
    tenant = getattr(request, 'tenant', None)
    if tenant and hasattr(model, 'tenant'):
        kwargs['tenant'] = tenant
    return get_object_or_404(model, **kwargs)
