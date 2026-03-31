import re

from django.conf import settings
from django.shortcuts import redirect


_EXEMPT_PATTERNS = [
    re.compile(r"^admin/login/?$"),
    re.compile(r"^admin/logout/?$"),
    re.compile(r"^admin/password_reset/"),
    re.compile(r"^static/"),
    re.compile(r"^favicon\.ico$"),
    # APIs não devem requerer autenticação
    re.compile(r"^api/"),
    # APIs da app "integracoes" (ex: /integracoes/api/lead/hubsoft-status/)
    re.compile(r"^integracoes/api/"),
    # Página de cadastro público
    re.compile(r"^cadastro/?$"),
    # Páginas de autenticação da aplicação
    re.compile(r"^login/?$"),
    re.compile(r"^logout/?$"),
    re.compile(r"^$"),  # Página inicial (home)
]


class LoginRequiredMiddleware:
    """Middleware que força autenticação nas páginas do painel.

    Exceções: páginas de login/logout (admin e aplicação), reset de senha, arquivos estáticos, 
    favicon, APIs, cadastro público e página inicial.
    Redireciona para settings.LOGIN_URL com parâmetro next.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path_no_slash = request.path.lstrip('/')

        # Sempre permitir as URLs isentas
        for pattern in _EXEMPT_PATTERNS:
            if pattern.match(path_no_slash):
                return self.get_response(request)

        # Se já autenticado, libera
        if request.user.is_authenticated:
            return self.get_response(request)

        # Redireciona para nossa página de login estilizada
        login_url = getattr(settings, 'LOGIN_URL', '/login/')
        return redirect(f"{login_url}?next={request.path}")


