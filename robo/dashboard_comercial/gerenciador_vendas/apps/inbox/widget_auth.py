"""
Autenticação e CORS para endpoints públicos do widget.

O widget se autentica via token público (UUID) no query parameter.
Não usa session, cookie ou Bearer token.
"""

import functools
import logging

from django.http import JsonResponse

from .models import WidgetConfig

logger = logging.getLogger(__name__)


def widget_token_required(view_func):
    """
    Decorator para views públicas do widget.

    1. Extrai token do query param ou body
    2. Resolve WidgetConfig + tenant
    3. Valida Origin contra dominios_permitidos
    4. Adiciona headers CORS na resposta
    5. Seta request.tenant e request.widget_config
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Handle CORS preflight
        if request.method == 'OPTIONS':
            return _cors_response(request, JsonResponse({}, status=200))

        # Extrair token
        token = request.GET.get('token') or request.POST.get('token')
        if not token:
            import json
            try:
                body = json.loads(request.body)
                token = body.get('token')
            except Exception:
                pass

        if not token:
            return JsonResponse({'error': 'Token obrigatório'}, status=403)

        # Resolver widget config
        widget_config = WidgetConfig.get_by_token(token)
        if not widget_config:
            return JsonResponse({'error': 'Token inválido ou widget desativado'}, status=403)

        # Validar Origin
        origin = request.META.get('HTTP_ORIGIN', '')
        dominios = widget_config.dominios_permitidos or []

        if dominios and origin:
            origin_host = origin.replace('https://', '').replace('http://', '').rstrip('/')
            permitido = any(
                origin_host == d or origin_host.endswith('.' + d)
                for d in dominios
            )
            if not permitido:
                logger.warning("Widget: origin %s rejeitado para token %s", origin, token)
                return JsonResponse({'error': 'Domínio não permitido'}, status=403)

        # Setar no request
        request.widget_config = widget_config
        request.tenant = widget_config.tenant

        # Executar view
        response = view_func(request, *args, **kwargs)

        # Adicionar CORS headers
        return _cors_response(request, response)

    return wrapper


def _cors_response(request, response):
    """Adiciona headers CORS à resposta."""
    origin = request.META.get('HTTP_ORIGIN', '*')
    response['Access-Control-Allow-Origin'] = origin
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Access-Control-Max-Age'] = '86400'
    return response
