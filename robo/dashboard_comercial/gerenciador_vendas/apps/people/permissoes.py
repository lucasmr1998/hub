"""
Guarda de acesso do modulo People.

Existe porque o `PermissaoMiddleware` do sistema so verifica FUNCIONALIDADE
(`acesso_people`), nunca o toggle de CONTRATACAO (`tenant.modulo_people`). O
gate de contratacao hoje e so visual, no `{% if modulo_people %}` da sidebar, o
que significa que quem digita a URL entra num modulo que a empresa nao comprou.

Aqui as duas condicoes andam juntas, do mesmo jeito que a sidebar ja faz nos
dois ramos do seu `{% if %}`. Vale inclusive pra superuser: se o tenant nao tem
o modulo, nao ha o que inspecionar ali.

Fica no app de proposito. Ensinar o middleware do sistema a olhar contratacao
mudaria o comportamento de todos os modulos de uma vez, e isso e decisao de
arquitetura, nao efeito colateral de entregar People.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse

from apps.sistema.decorators import user_tem_funcionalidade


def tenant_tem_people(request):
    """True se a empresa contratou o modulo. Sem tenant no request, nao bloqueia."""
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return True
    return bool(getattr(tenant, 'modulo_people', False))


def pode_acessar(request, funcionalidade='people.ver'):
    return tenant_tem_people(request) and user_tem_funcionalidade(request, funcionalidade)


def requer_people(funcionalidade='people.ver', json=False):
    """
    Decorator das views do People.

    Uso:
        @requer_people()
        def board(request): ...

        @requer_people('people.mover_colaborador', json=True)
        def api_mover(request, pk): ...
    """
    def decorador(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not tenant_tem_people(request):
                return _negar('Esta empresa nao contratou o modulo People.', json)
            if not user_tem_funcionalidade(request, funcionalidade):
                return _negar('Sem permissao pra esta acao no People.', json)
            return view(request, *args, **kwargs)
        return wrapper
    return decorador


def _negar(mensagem, json):
    if json:
        return JsonResponse({'erro': mensagem}, status=403)
    return HttpResponseForbidden(mensagem)
