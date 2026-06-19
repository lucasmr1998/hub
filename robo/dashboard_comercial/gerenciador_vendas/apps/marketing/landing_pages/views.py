"""
Views da Landing Page.

- landing_publica: GET da LP pelo slug do tenant + slug da landing
- submeter_formulario: POST do form, valida campos via catalog/validators,
  cria LeadProspecto + LandingSubmissao + dispara signal lead_criado.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.sistema.models import Tenant

from .catalog import get_campo, listar_blocos, listar_campos
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


# ============================================================================
# ADMIN — listas + editor
# ============================================================================

def _slug_unico(tenant, base: str) -> str:
    """Garante slug unico por tenant no LandingPage."""
    base = slugify(base) or 'nova-pagina'
    candidato, i = base, 2
    while LandingPage.objects.filter(slug=candidato).exists():
        candidato = f'{base}-{i}'
        i += 1
    return candidato


@login_required
def admin_lista_lps(request):
    """Lista as Landing Pages do tenant."""
    qs = LandingPage.objects.all().select_related('campanha_padrao').order_by('-atualizado_em')
    busca = (request.GET.get('q') or '').strip()
    if busca:
        qs = qs.filter(nome__icontains=busca) | qs.filter(slug__icontains=busca)
    status_filtro = request.GET.get('status') or ''
    if status_filtro:
        qs = qs.filter(status=status_filtro)
    return render(request, 'landing_pages/admin/lista_lps.html', {
        'page_title': 'Landing Pages',
        'lps': qs[:200],
        'busca': busca,
        'status_filtro': status_filtro,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def admin_criar_lp(request):
    """Cria nova Landing Page (form simples). Apos criar, redireciona pro editor."""
    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        slug = (request.POST.get('slug') or '').strip()
        if not nome:
            return render(request, 'landing_pages/admin/criar_lp.html', {
                'erro': 'Nome obrigatorio', 'nome_pre': nome, 'slug_pre': slug,
            })
        slug = _slug_unico(request.tenant, slug or nome)
        lp = LandingPage.objects.create(
            nome=nome[:200],
            slug=slug,
            status='rascunho',
            blocos_json=[],
            criado_por=request.user,
        )
        return redirect('landing_pages_admin:editar_lp', pk=lp.pk)
    return render(request, 'landing_pages/admin/criar_lp.html', {
        'page_title': 'Nova Landing Page',
    })


@login_required
def admin_editar_lp(request, pk: int):
    """Editor visual da LP — drag-drop dos blocos."""
    lp = get_object_or_404(LandingPage.objects.all(), pk=pk)

    # Catalogo de blocos pra paleta lateral (incluindo categoria + label)
    catalogo = [
        {
            'slug': b.slug,
            'label': b.label,
            'categoria': b.categoria,
            'descricao': b.descricao,
            'defaults': b.defaults,
            'schema': b.schema,
        }
        for b in listar_blocos()
    ]
    # Formularios disponiveis pro bloco `form`
    formularios = list(FormularioLanding.objects.all().values('id', 'nome'))

    return render(request, 'landing_pages/admin/editar_lp.html', {
        'page_title': f'Editor — {lp.nome}',
        'lp': lp,
        'catalogo_blocos': catalogo,
        'catalogo_blocos_json': json.dumps(catalogo, ensure_ascii=False),
        'formularios_json': json.dumps(formularios, ensure_ascii=False),
        'blocos_json': json.dumps(lp.blocos_json or [], ensure_ascii=False),
    })


@login_required
@require_POST
def admin_salvar_lp(request, pk: int):
    """API JSON — salva blocos_json + config_json + status."""
    lp = get_object_or_404(LandingPage.objects.all(), pk=pk)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'erro': 'JSON invalido'}, status=400)

    if 'blocos_json' in payload and isinstance(payload['blocos_json'], list):
        lp.blocos_json = payload['blocos_json']
    if 'config_json' in payload and isinstance(payload['config_json'], dict):
        lp.config_json = payload['config_json']
    if 'nome' in payload:
        lp.nome = str(payload['nome'])[:200]
    if 'seo_title' in payload:
        lp.seo_title = str(payload['seo_title'])[:200]
    if 'seo_description' in payload:
        lp.seo_description = str(payload['seo_description'])[:300]
    if 'status' in payload and payload['status'] in ('rascunho', 'publicada', 'arquivada'):
        lp.status = payload['status']
        if payload['status'] == 'publicada' and not lp.publicado_em:
            lp.publicado_em = timezone.now()
    # Invalida cache do html_compilado quando edita
    lp.html_compilado = ''
    lp.save()
    return JsonResponse({'ok': True, 'lp_id': lp.pk})


@login_required
@require_POST
def admin_excluir_lp(request, pk: int):
    lp = get_object_or_404(LandingPage.objects.all(), pk=pk)
    lp.delete()
    return redirect('landing_pages_admin:lista_lps')


# ----- Formularios -----

@login_required
def admin_lista_forms(request):
    qs = FormularioLanding.objects.all().order_by('-atualizado_em')
    busca = (request.GET.get('q') or '').strip()
    if busca:
        qs = qs.filter(nome__icontains=busca)
    return render(request, 'landing_pages/admin/lista_forms.html', {
        'page_title': 'Formularios',
        'formularios': qs[:200],
        'busca': busca,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def admin_criar_form(request):
    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        if not nome:
            return render(request, 'landing_pages/admin/criar_form.html', {
                'erro': 'Nome obrigatorio', 'nome_pre': nome,
            })
        form = FormularioLanding.objects.create(
            nome=nome[:200],
            campos_json=[],
            submit_label='Enviar',
        )
        return redirect('landing_pages_admin:editar_form', pk=form.pk)
    return render(request, 'landing_pages/admin/criar_form.html', {
        'page_title': 'Novo Formulario',
    })


@login_required
def admin_editar_form(request, pk: int):
    form = get_object_or_404(FormularioLanding.objects.all(), pk=pk)
    catalogo = [
        {
            'slug': c.slug,
            'label': c.label,
            'descricao': c.descricao,
            'defaults': c.defaults,
            'schema': c.schema,
            'validador': c.validador,
        }
        for c in listar_campos()
    ]
    return render(request, 'landing_pages/admin/editar_form.html', {
        'page_title': f'Editor — {form.nome}',
        'form_obj': form,
        'catalogo_campos': catalogo,
        'catalogo_campos_json': json.dumps(catalogo, ensure_ascii=False),
        'campos_json': json.dumps(form.campos_json or [], ensure_ascii=False),
    })


@login_required
@require_POST
def admin_salvar_form(request, pk: int):
    form = get_object_or_404(FormularioLanding.objects.all(), pk=pk)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'erro': 'JSON invalido'}, status=400)
    if 'campos_json' in payload and isinstance(payload['campos_json'], list):
        form.campos_json = payload['campos_json']
    if 'nome' in payload:
        form.nome = str(payload['nome'])[:200]
    if 'submit_label' in payload:
        form.submit_label = str(payload['submit_label'])[:80]
    if 'success_msg' in payload:
        form.success_msg = str(payload['success_msg'])
    if 'success_redirect' in payload:
        form.success_redirect = str(payload['success_redirect'])[:200]
    if 'bloquear_fora_cobertura' in payload:
        form.bloquear_fora_cobertura = bool(payload['bloquear_fora_cobertura'])
    form.save()
    return JsonResponse({'ok': True, 'form_id': form.pk})


@login_required
@require_POST
def admin_excluir_form(request, pk: int):
    form = get_object_or_404(FormularioLanding.objects.all(), pk=pk)
    form.delete()
    return redirect('landing_pages_admin:lista_forms')


@login_required
@require_GET
def admin_preview_lp(request, pk: int):
    """Renderiza HTML da LP usando o renderer (mesmo do publico) — pra iframe do editor."""
    lp = get_object_or_404(LandingPage.objects.all(), pk=pk)
    html = renderizar_landing(lp, request=request)
    return HttpResponse(html)


@login_required
@require_POST
def admin_render_blocos_html(request):
    """Renderiza HTML de uma lista de blocos. Usado pelo editor pra preview ao vivo."""
    from .renderer import renderizar_blocos
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'erro': 'JSON invalido'}, status=400)
    blocos = payload.get('blocos_json') or []
    if not isinstance(blocos, list):
        return JsonResponse({'ok': False, 'erro': 'blocos_json deve ser lista'}, status=400)
    html = renderizar_blocos(blocos, request=request)
    return JsonResponse({'ok': True, 'html': html})
