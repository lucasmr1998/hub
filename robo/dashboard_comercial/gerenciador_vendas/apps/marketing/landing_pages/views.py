"""
Views da Landing Page.

- landing_publica: GET da LP pelo slug do tenant + slug da landing
- submeter_formulario: POST do form, valida campos via catalog/validators,
  cria LeadProspecto + LandingSubmissao + dispara signal lead_criado.
"""
from __future__ import annotations

import logging

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta

from apps.sistema.models import Tenant

from .catalog import get_campo
from .models import FormularioLanding, LandingPage, LandingSubmissao
from .renderer import renderizar_landing
from .validators import get_validador

logger = logging.getLogger(__name__)


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

    if landing.html_compilado:
        return HttpResponse(landing.html_compilado)

    html = renderizar_landing(landing, request=request)
    return HttpResponse(html)


def _ip_origem(request) -> str:
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if fwd:
        return fwd.split(',')[0].strip()[:64]
    return (request.META.get('REMOTE_ADDR') or '')[:64]


def _coletar_endereco(post: dict) -> dict:
    """Reconstroi o dict de endereco a partir de campos `endereco[rua]`, etc."""
    end = {}
    for chave in ('rua', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'referencia'):
        valor = post.get(f'endereco[{chave}]') or post.get(chave) or ''
        if valor:
            end[chave] = valor
    return end


@csrf_exempt
@require_POST
def submeter_formulario(request, tenant_slug: str, landing_slug: str):
    """Processa submit do form da LP. Cria LeadProspecto + LandingSubmissao."""
    try:
        tenant = Tenant.objects.get(slug=tenant_slug, ativo=True)
    except Tenant.DoesNotExist:
        return JsonResponse({'ok': False, 'erro': 'Tenant invalido'}, status=404)

    try:
        landing = LandingPage.all_tenants.get(tenant=tenant, slug=landing_slug, status='publicada')
    except LandingPage.DoesNotExist:
        return JsonResponse({'ok': False, 'erro': 'Landing nao encontrada ou nao publicada'}, status=404)

    form_id = request.POST.get('formulario_id')
    try:
        formulario = FormularioLanding.all_tenants.get(tenant=tenant, pk=int(form_id))
    except (ValueError, TypeError, FormularioLanding.DoesNotExist):
        return JsonResponse({'ok': False, 'erro': 'Formulario invalido'}, status=400)

    # Valida cada campo do formulario
    dados_validados: dict = {}
    erros: list[str] = []
    endereco_dict = _coletar_endereco(request.POST)

    for campo in formulario.campos_json or []:
        if not isinstance(campo, dict):
            continue
        tipo = campo.get('tipo')
        spec = get_campo(tipo)
        if not spec:
            continue
        # Mescla props default + custom
        props_full = dict(spec.defaults)
        props_full.update(campo.get('props', {}))
        if 'name' in campo:
            props_full['name'] = campo['name']
        nome_field = props_full.get('name', '')
        # Valor do campo
        if tipo == 'endereco':
            valor_raw = endereco_dict
        elif tipo == 'viabilidade':
            # Reconstrói a partir do CEP + endereco que ja foram preenchidos no form
            valor_raw = {
                'cep': request.POST.get('cep', ''),
                **endereco_dict,
            }
        else:
            valor_raw = request.POST.get(nome_field, '')

        validador = get_validador(spec.validador)
        if validador:
            valor, erro = validador(valor_raw, {'tipo': tipo, 'props': props_full}, tenant)
            if erro:
                erros.append(erro)
            dados_validados[nome_field or tipo] = valor
        else:
            dados_validados[nome_field or tipo] = valor_raw

    # Bloqueio por viabilidade
    if formulario.bloquear_fora_cobertura:
        via = dados_validados.get('viabilidade', {})
        if isinstance(via, dict) and via.get('status') == 'fora_cobertura':
            return JsonResponse({
                'ok': False,
                'erros': ['Infelizmente ainda nao atendemos seu endereco.'],
            }, status=400)

    if erros:
        return JsonResponse({'ok': False, 'erros': erros}, status=400)

    # Cria/atualiza LeadProspecto
    lead = None
    if formulario.criar_lead:
        lead = _criar_ou_atualizar_lead(tenant, dados_validados, landing)

    # Salva LandingSubmissao
    sub = LandingSubmissao.objects.create(
        tenant=tenant,
        landing=landing,
        formulario=formulario,
        lead=lead,
        dados_form=dados_validados,
        utm_source=request.GET.get('utm_source', '')[:100],
        utm_medium=request.GET.get('utm_medium', '')[:100],
        utm_campaign=request.GET.get('utm_campaign', '')[:200],
        utm_content=request.GET.get('utm_content', '')[:200],
        utm_term=request.GET.get('utm_term', '')[:200],
        ip_origem=_ip_origem(request),
        user_agent=(request.META.get('HTTP_USER_AGENT', '') or '')[:500],
        referrer=(request.META.get('HTTP_REFERER', '') or '')[:1000],
    )
    logger.info('[LP] submissao %s criada (lead=%s)', sub.pk, lead.pk if lead else None)

    payload = {
        'ok': True,
        'submissao_id': sub.pk,
        'lead_id': lead.pk if lead else None,
        'mensagem': formulario.success_msg,
    }
    if formulario.success_redirect:
        payload['redirect'] = formulario.success_redirect
    return JsonResponse(payload)


def _criar_ou_atualizar_lead(tenant, dados: dict, landing):
    """Cria LeadProspecto ou atualiza se telefone ja existe na ultima hora."""
    from apps.comercial.leads.models import LeadProspecto

    telefone = dados.get('telefone', '')
    nome = dados.get('nome', '') or dados.get('nome_razaosocial', '')
    email = dados.get('email', '')
    cpf = dados.get('cpf_cnpj', '')
    endereco = dados.get('endereco', {}) if isinstance(dados.get('endereco'), dict) else {}

    # Dedup: mesmo telefone na ultima hora -> atualiza
    desde = timezone.now() - timedelta(hours=1)
    lead = LeadProspecto.all_tenants.filter(
        tenant=tenant, telefone=telefone, data_cadastro__gte=desde,
    ).order_by('-id').first() if telefone else None

    fields = dict(
        nome_razaosocial=nome[:200] if nome else (telefone or 'Sem nome'),
        telefone=telefone,
        email=email,
        cpf_cnpj=cpf,
        cep=dados.get('cep', ''),
        rua=endereco.get('rua', ''),
        numero_residencia=endereco.get('numero', ''),
        bairro=endereco.get('bairro', ''),
        cidade=endereco.get('cidade', ''),
        estado=endereco.get('uf', ''),
        ponto_referencia=endereco.get('referencia', ''),
        origem='landing_page',
    )

    if lead:
        for k, v in fields.items():
            if v:
                setattr(lead, k, v)
        lead.save()
    else:
        lead = LeadProspecto(
            tenant=tenant,
            status_api=LeadProspecto.status_api_inicial(tenant),
            **fields,
        )
        lead._skip_segmento = True
        lead.save()

    # Atribuicao por campanha
    if landing.campanha_padrao_id and not lead.campanha_origem_id:
        LeadProspecto.all_tenants.filter(pk=lead.pk).update(
            campanha_origem_id=landing.campanha_padrao_id,
        )
    return lead
