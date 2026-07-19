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
    # APIs da app "ia_validador" (acessadas pela API IA externa FastAPI)
    re.compile(r"^ia_validador/api/"),
    # Página de cadastro público e acompanhamento
    re.compile(r"^cadastro/?$"),
    re.compile(r"^acompanhamento/\d+/?$"),
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
        # path_info exclui o SCRIPT_NAME (/robo-v2 no TecHub), então os
        # padrões de isenção funcionam igual na raiz e sob subpath.
        path_no_slash = request.path_info.lstrip('/')

        # Sempre permitir as URLs isentas
        for pattern in _EXEMPT_PATTERNS:
            if pattern.match(path_no_slash):
                return self.get_response(request)

        # Se já autenticado, libera — MAS usuário sem Perfil de Acesso (e não
        # superuser) não tem o uso liberado: vê a página de acesso pendente.
        # Usuários vêm do portal TecHub; o admin concede o perfil em /crm/perfis/.
        if request.user.is_authenticated:
            try:
                from vendas_web.rbac import capacidades_do_usuario
                if (not request.user.is_superuser
                        and not capacidades_do_usuario(request.user)):
                    from django.shortcuts import render
                    return render(request, 'vendas_web/sem_acesso.html', {}, status=403)
            except Exception:
                pass
            return self.get_response(request)

        # Redireciona para nossa página de login estilizada
        login_url = getattr(settings, 'LOGIN_URL', '/login/')
        return redirect(f"{login_url}?next={request.path}")


