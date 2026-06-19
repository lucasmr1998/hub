"""
Views da Landing Page.

Fase 1: view publica que renderiza LP pelo slug do tenant + slug da LP.
URL: /p/<tenant_slug>/<landing_slug>/

Fase 2 vai adicionar: view de submit do form, view admin de listagem/editor.
"""
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control

from apps.sistema.models import Tenant

from .models import LandingPage
from .renderer import renderizar_landing


@cache_control(max_age=60, public=True)
def landing_publica(request, tenant_slug: str, landing_slug: str):
    """View publica da LP. Acesso por slug do tenant + slug da landing."""
    try:
        tenant = Tenant.objects.get(slug=tenant_slug, ativo=True)
    except Tenant.DoesNotExist:
        raise Http404('Tenant nao encontrado')

    landing = get_object_or_404(
        LandingPage.all_tenants.filter(tenant=tenant),
        slug=landing_slug,
        status='publicada',
    )

    # Se ja tem html_compilado, usa direto (mais rapido)
    if landing.html_compilado:
        return HttpResponse(landing.html_compilado)

    # Senao, renderiza on-the-fly
    html = renderizar_landing(landing, request=request)
    return HttpResponse(html)
