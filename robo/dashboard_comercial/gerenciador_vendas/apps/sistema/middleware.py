import re
import threading

from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


# ── Login Required Middleware ────────────────────────────────────────────────

_EXEMPT_PATTERNS = [
    re.compile(r"^admin/login/?$"),
    re.compile(r"^admin/logout/?$"),
    re.compile(r"^admin/password_reset/"),
    re.compile(r"^static/"),
    re.compile(r"^favicon\.ico$"),
    re.compile(r"^api/"),
    re.compile(r"^integracoes/api/"),
    re.compile(r"^cadastro/?$"),
    re.compile(r"^login/?$"),
    re.compile(r"^logout/?$"),
    re.compile(r"^$"),
]


class LoginRequiredMiddleware:
    """Força autenticação nas páginas do painel.

    Exceções: login/logout, admin, reset de senha, arquivos estáticos,
    favicon, APIs, cadastro público e página inicial.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path_no_slash = request.path.lstrip('/')

        for pattern in _EXEMPT_PATTERNS:
            if pattern.match(path_no_slash):
                return self.get_response(request)

        if request.user.is_authenticated:
            return self.get_response(request)

        login_url = getattr(settings, 'LOGIN_URL', '/login/')
        return redirect(f"{login_url}?next={request.path}")


# ── Tenant Middleware ────────────────────────────────────────────────────────

_thread_locals = threading.local()


def get_current_tenant():
    """Retorna o tenant do request atual (ou None fora de request)."""
    return getattr(_thread_locals, 'tenant', None)


def set_current_tenant(tenant):
    """Define o tenant manualmente (útil em management commands e tasks)."""
    _thread_locals.tenant = tenant


class TenantMiddleware(MiddlewareMixin):
    """
    Identifica o tenant do request a partir do PerfilUsuario logado.
    Injeta request.tenant e armazena em thread-local para o TenantManager.
    Redireciona ao setup inicial se o tenant não tem configuração.
    """

    SETUP_URL = '/setup/'
    SKIP_PATHS = ('/setup/', '/login/', '/logout/', '/admin/', '/static/', '/media/')

    def process_request(self, request):
        tenant = None

        if hasattr(request, 'user') and request.user.is_authenticated:
            perfil = getattr(request.user, 'perfil', None)
            if perfil:
                tenant = perfil.tenant

        request.tenant = tenant
        _thread_locals.tenant = tenant

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Redireciona ao setup se tenant não tem ConfiguracaoEmpresa."""
        if not request.tenant:
            return None

        # Não redirecionar em paths do setup, login, admin, etc.
        if any(request.path.startswith(p) for p in self.SKIP_PATHS):
            return None

        # Não redirecionar em chamadas de API
        if '/api/' in request.path:
            return None

        # Verificar se tem configuração
        from apps.sistema.models import ConfiguracaoEmpresa
        has_config = ConfiguracaoEmpresa.all_tenants.filter(
            tenant=request.tenant, ativo=True
        ).exists()

        if not has_config:
            return redirect('sistema:setup_inicial')

        return None

    def process_response(self, request, response):
        _thread_locals.tenant = None
        return response
