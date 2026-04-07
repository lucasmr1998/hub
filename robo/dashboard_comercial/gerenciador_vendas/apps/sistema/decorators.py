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
    """Valida token de API no header Authorization para integracoes externas.

    Espera: Authorization: Bearer <token>
    Fluxo: busca token por tenant no banco, fallback para env var global.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Token obrigatorio'}, status=401)

        token = auth_header[7:].strip()

        # 1. Buscar token por tenant no banco
        try:
            from apps.integracoes.models import IntegracaoAPI
            integracao = IntegracaoAPI.all_tenants.filter(
                api_token=token, ativa=True,
            ).select_related('tenant').first()
            if integracao and integracao.tenant:
                request.tenant = integracao.tenant
                from apps.sistema.middleware import _thread_local
                _thread_local.tenant = integracao.tenant
                return view_func(request, *args, **kwargs)
        except Exception:
            pass

        # 2. Fallback: token global N8N
        n8n_token = os.environ.get('N8N_API_TOKEN', '')
        if n8n_token and token == n8n_token:
            return view_func(request, *args, **kwargs)

        # 3. Fallback: webhook token
        webhook_token = os.environ.get('WEBHOOK_SECRET_TOKEN', '')
        if webhook_token and token == webhook_token:
            return view_func(request, *args, **kwargs)

        return JsonResponse({'error': 'Token invalido'}, status=401)
    return wrapper


def permissao_required(modulo, papel_minimo=None):
    """
    Decorator que verifica se o usuário tem acesso ao módulo e papel mínimo.
    Superusers sempre passam.

    Uso:
        @permissao_required('comercial')              # apenas acesso ao módulo
        @permissao_required('comercial', 'supervisor') # supervisor ou gerente
        @permissao_required('inbox', 'gerente')        # só gerente
    """
    HIERARQUIA = {
        'comercial': ['vendedor', 'supervisor', 'gerente'],
        'marketing': ['analista', 'gerente'],
        'cs': ['operador', 'gerente'],
        'inbox': ['agente', 'supervisor', 'gerente'],
    }

    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                from django.shortcuts import redirect
                return redirect('login')

            # Superuser bypassa tudo
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Buscar permissões
            from apps.sistema.models import PermissaoUsuario
            perm = PermissaoUsuario.get_for_user(user)
            if perm is None:
                logger.warning("[PERMISSÃO] Usuário %s sem PermissaoUsuario, acesso negado a %s", user.username, modulo)
                return JsonResponse({'error': 'Sem permissões configuradas'}, status=403)

            # Camada 1: acesso ao módulo
            if modulo == 'configuracoes':
                if not perm.acesso_configuracoes:
                    return JsonResponse({'error': 'Sem acesso às configurações'}, status=403)
                return view_func(request, *args, **kwargs)

            campo_acesso = f'acesso_{modulo}'
            if not getattr(perm, campo_acesso, False):
                return JsonResponse({'error': f'Sem acesso ao módulo {modulo}'}, status=403)

            # Camada 2: papel mínimo
            if papel_minimo and modulo in HIERARQUIA:
                papel_atual = getattr(perm, f'papel_{modulo}', '')
                hierarquia = HIERARQUIA[modulo]
                if papel_atual not in hierarquia:
                    return JsonResponse({'error': 'Papel inválido'}, status=403)
                nivel_atual = hierarquia.index(papel_atual)
                nivel_minimo = hierarquia.index(papel_minimo)
                if nivel_atual < nivel_minimo:
                    return JsonResponse({'error': f'Requer pelo menos {papel_minimo}'}, status=403)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def user_tem_funcionalidade(request, codigo):
    """
    Verifica se o usuário do request tem a funcionalidade.
    Superuser e sem perfil (legado) = True.
    Usa o cache do PermissaoMiddleware (request.user_funcionalidades).

    Uso nas views:
        if not user_tem_funcionalidade(request, 'comercial.configurar_pipeline'):
            return JsonResponse({'error': 'Sem permissão'}, status=403)
    """
    if request.user.is_superuser:
        return True
    funcs = getattr(request, 'user_funcionalidades', None)
    if funcs is None:  # None = sem perfil (legado), tudo liberado
        return True
    return codigo in funcs


def get_tenant_object_or_404(model, request, **kwargs):
    """Get object filtered by current tenant. Raises 404 if not found or wrong tenant."""
    tenant = getattr(request, 'tenant', None)
    if tenant and hasattr(model, 'tenant'):
        kwargs['tenant'] = tenant
    return get_object_or_404(model, **kwargs)
