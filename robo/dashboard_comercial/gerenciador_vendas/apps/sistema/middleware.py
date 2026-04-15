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
    re.compile(r"^inbox/api/uazapi/webhook/"),
    re.compile(r"^inbox/api/webhook/"),
    re.compile(r"^assistente/webhook/"),
    re.compile(r"^cadastro/?$"),
    re.compile(r"^login/?$"),
    re.compile(r"^logout/?$"),
    re.compile(r"^$"),
    re.compile(r"^health/?$"),
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
            # Forçar troca de senha temporária
            perfil = getattr(request.user, 'perfil', None)
            if perfil and perfil.senha_temporaria and path_no_slash != 'trocar-senha/':
                return redirect('/trocar-senha/')
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


# ── Permissão Middleware ───────────────────────────────────────────────────

# Mapeamento: prefixo de URL → (campo de acesso, campo de papel mínimo para config)
_MODULO_MAP = [
    ('/crm/', 'acesso_comercial'),
    ('/comercial/', 'acesso_comercial'),
    ('/marketing/', 'acesso_marketing'),
    ('/cs/', 'acesso_cs'),
    ('/roleta/', 'acesso_cs'),
    ('/inbox/', 'acesso_inbox'),
    ('/suporte/', 'acesso_inbox'),
    ('/configuracoes', 'acesso_configuracoes'),
]

_PERM_SKIP_PATHS = (
    '/login/', '/logout/', '/admin/', '/aurora-admin/', '/static/', '/media/',
    '/api/', '/setup/', '/cadastro/',
)


class PermissaoMiddleware:
    """
    Verifica permissões por módulo baseado na URL.
    Superusers e usuários sem PermissaoUsuario (legado) passam livremente.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Só verifica em requests autenticados
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return self.get_response(request)

        # Superuser passa tudo
        if request.user.is_superuser:
            return self.get_response(request)

        # Pular paths isentos
        if any(request.path.startswith(p) for p in _PERM_SKIP_PATHS):
            return self.get_response(request)

        # Buscar permissões
        from apps.sistema.models import PermissaoUsuario
        perm = PermissaoUsuario.get_for_user(request.user)

        # Se não tem PermissaoUsuario cadastrado, passa (retrocompatibilidade)
        if perm is None:
            request.user_funcionalidades = None  # None = tudo liberado
            return self.get_response(request)

        # Cachear códigos de funcionalidade no request (evita N+1)
        if perm.perfil:
            request.user_funcionalidades = set(
                perm.perfil.funcionalidades.values_list('codigo', flat=True)
            )
        else:
            request.user_funcionalidades = set()

        # Verificar módulo pela URL
        for prefixo, campo_acesso in _MODULO_MAP:
            if prefixo in request.path:
                if not getattr(perm, campo_acesso, False):
                    from django.http import HttpResponseForbidden
                    return HttpResponseForbidden(
                        '<h2>Acesso negado</h2>'
                        '<p>Você não tem permissão para acessar este módulo. '
                        'Contate o administrador.</p>'
                    )
                break

        # Atualizar atividade do agente (para auto-offline)
        try:
            from apps.inbox.models import PerfilAgenteInbox
            from django.utils import timezone
            from datetime import timedelta
            perfil_agente = PerfilAgenteInbox.objects.filter(user=request.user).first()
            if perfil_agente:
                agora = timezone.now()
                if perfil_agente.status == 'online' and perfil_agente.ultimo_status_em:
                    if agora - perfil_agente.ultimo_status_em > timedelta(minutes=30):
                        perfil_agente.status = 'offline'
                        perfil_agente.save(update_fields=['status', 'ultimo_status_em'])
                elif perfil_agente.status in ('online', 'ausente'):
                    if not perfil_agente.ultimo_status_em or agora - perfil_agente.ultimo_status_em > timedelta(minutes=1):
                        perfil_agente.save(update_fields=['ultimo_status_em'])
        except Exception:
            pass

        return self.get_response(request)
