"""Resolucao de tenant a partir do token na URL (/robo/<token>/...).

O Matrix de cada empresa chama a URL com o token dela. O token e o `api_token`
de uma IntegracaoAPI ativa, o mesmo mecanismo do decorators.api_token_required,
so que lido do path em vez do header Authorization. Assim o corpo que o Matrix
envia nao muda: apenas o prefixo da URL identifica a empresa.
"""
import functools

from django.http import JsonResponse


def resolver_tenant_por_token(token):
    """Retorna o tenant dono do `api_token` (integracao ativa), ou None.

    Usa `all_tenants` (sem filtro de tenant), pois aqui ainda nao ha tenant no
    contexto (a request e de maquina, sem usuario logado).
    """
    if not token:
        return None
    try:
        from apps.integracoes.models import IntegracaoAPI
        integ = (
            IntegracaoAPI.all_tenants
            .filter(api_token=token, ativa=True)
            .select_related('tenant')
            .first()
        )
        if integ and integ.tenant:
            return integ.tenant
    except Exception:
        return None
    return None


def tenant_por_token_url(view_func):
    """Decorator: resolve o tenant do kwarg `token` da URL e injeta em request.tenant.

    Seta tambem o thread-local pra o TenantManager filtrar as queries (`.objects`)
    automaticamente, ja que fora de request logado o middleware nao resolve tenant.
    Responde 401 se o token nao casar com nenhuma integracao ativa.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tenant = resolver_tenant_por_token(kwargs.get('token', ''))
        if tenant is None:
            return JsonResponse({'error': 'Token invalido'}, status=401)
        request.tenant = tenant
        from apps.sistema.middleware import _thread_locals
        _thread_locals.tenant = tenant
        return view_func(request, *args, **kwargs)
    return wrapper
