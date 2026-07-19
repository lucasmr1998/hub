"""Views do adaptador de contrato Matrix (robo_matrix).

Fase 0: apenas o ping que confirma a resolucao de tenant pelo token na URL e o
isolamento entre empresas. Os endpoints de contrato do robo_v2
(/proximo-passo, /validar, /recontato, /validar-imagem) entram na Fase 1.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .auth import tenant_por_token_url


@csrf_exempt
@tenant_por_token_url
@require_http_methods(["GET", "POST"])
def ping(request, token):
    """Confirma que o token resolveu o tenant certo. Diagnostico de Fase 0."""
    tenant = request.tenant
    return JsonResponse({
        'ok': True,
        'tenant_id': tenant.id,
        'tenant_slug': getattr(tenant, 'slug', ''),
        'tenant_nome': getattr(tenant, 'nome', ''),
    })
