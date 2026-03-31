from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.sistema.models import (
    Tenant, PerfilUsuario, ConfiguracaoEmpresa, LogSistema,
    Plano, FeaturePlano,
)


def staff_required(view_func):
    return user_passes_test(lambda u: u.is_staff)(login_required(view_func))


def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(login_required(view_func))


def _user_can_access_tenant(user, tenant_id):
    """Check if user can access a specific tenant. Superusers can access all."""
    if user.is_superuser:
        return True
    perfil = PerfilUsuario.objects.filter(user=user).first()
    return perfil and perfil.tenant_id == tenant_id


@superuser_required
def dashboard_view(request):
    """Dashboard principal do admin Aurora. Somente superusers."""
    tenants = Tenant.objects.all()
    total_tenants = tenants.count()
    ativos = tenants.filter(ativo=True).count()
    em_trial = tenants.filter(em_trial=True).count()
    trials_expirando = tenants.filter(
        em_trial=True,
        trial_fim__lte=date.today() + timedelta(days=3),
        trial_fim__gte=date.today(),
    ).count()

    from apps.comercial.leads.models import LeadProspecto
    tenant_data = []
    for t in tenants.order_by('-ativo', 'nome'):
        leads = LeadProspecto.all_tenants.filter(tenant=t).count()
        users = PerfilUsuario.objects.filter(tenant=t).count()
        config = ConfiguracaoEmpresa.all_tenants.filter(tenant=t, ativo=True).first()
        tenant_data.append({
            'tenant': t,
            'leads': leads,
            'users': users,
            'config': config,
        })

    erros_recentes = LogSistema.all_tenants.filter(
        nivel__in=['ERROR', 'CRITICAL'],
        data_criacao__gte=timezone.now() - timedelta(hours=24),
    ).count()

    return render(request, 'admin_aurora/dashboard.html', {
        'total_tenants': total_tenants,
        'ativos': ativos,
        'em_trial': em_trial,
        'trials_expirando': trials_expirando,
        'erros_recentes': erros_recentes,
        'tenant_data': tenant_data,
    })


@staff_required
def tenant_detalhe_view(request, tenant_id):
    """Detalhe e edição de um tenant."""
    if not _user_can_access_tenant(request.user, tenant_id):
        return HttpResponseForbidden("Acesso negado a este tenant.")
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    config = ConfiguracaoEmpresa.all_tenants.filter(tenant=tenant, ativo=True).first()
    users = PerfilUsuario.objects.filter(tenant=tenant).select_related('user')

    from apps.comercial.leads.models import LeadProspecto
    from apps.integracoes.models import IntegracaoAPI
    leads_count = LeadProspecto.all_tenants.filter(tenant=tenant).count()
    integracao = IntegracaoAPI.objects.filter(tipo='hubsoft').first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'atualizar_modulos':
            tenant.modulo_comercial = request.POST.get('modulo_comercial') == 'on'
            tenant.modulo_marketing = request.POST.get('modulo_marketing') == 'on'
            tenant.modulo_cs = request.POST.get('modulo_cs') == 'on'
            tenant.plano_comercial = request.POST.get('plano_comercial', 'starter')
            tenant.plano_marketing = request.POST.get('plano_marketing', 'starter')
            tenant.plano_cs = request.POST.get('plano_cs', 'starter')
            tenant.save()

        elif action == 'toggle_ativo':
            tenant.ativo = not tenant.ativo
            tenant.save()

        elif action == 'estender_trial':
            dias = int(request.POST.get('dias_trial', 14))
            tenant.em_trial = True
            tenant.trial_inicio = date.today()
            tenant.trial_fim = date.today() + timedelta(days=dias)
            tenant.save()

        elif action == 'encerrar_trial':
            tenant.em_trial = False
            tenant.save()

        return redirect('admin_aurora:tenant_detalhe', tenant_id=tenant.pk)

    return render(request, 'admin_aurora/tenant_detalhe.html', {
        'tenant': tenant,
        'config': config,
        'users': users,
        'leads_count': leads_count,
        'integracao': integracao,
    })


@superuser_required
def criar_tenant_view(request):
    """Criar novo tenant via UI. Somente superusers."""
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        cnpj = request.POST.get('cnpj', '').strip()
        plano = request.POST.get('plano', 'comercial_start')
        admin_user = request.POST.get('username', '').strip()
        admin_email = request.POST.get('email', '').strip()
        admin_senha = request.POST.get('senha', '').strip()
        trial = request.POST.get('trial') == 'on'

        erros = []
        if not nome:
            erros.append('Nome é obrigatório.')
        if not admin_user:
            erros.append('Username é obrigatório.')
        if not admin_email:
            erros.append('Email é obrigatório.')
        if not admin_senha:
            erros.append('Senha é obrigatória.')
        if admin_user and User.objects.filter(username=admin_user).exists():
            erros.append(f'Username "{admin_user}" já existe.')

        slug = slugify(nome) if nome else ''
        if slug and Tenant.objects.filter(slug=slug).exists():
            erros.append(f'Tenant com slug "{slug}" já existe.')

        if erros:
            return render(request, 'admin_aurora/criar_tenant.html', {
                'erros': erros,
                'form': request.POST,
            })

        plano_map = {
            'comercial_starter': {'comercial': True, 'plano_comercial': 'starter'},
            'comercial_start': {'comercial': True, 'plano_comercial': 'start'},
            'comercial_pro': {'comercial': True, 'plano_comercial': 'pro'},
        }
        cfg = plano_map.get(plano, plano_map['comercial_start'])

        tenant = Tenant.objects.create(
            nome=nome,
            slug=slug,
            cnpj=cnpj or None,
            modulo_comercial=cfg.get('comercial', True),
            plano_comercial=cfg.get('plano_comercial', 'start'),
            ativo=True,
            em_trial=trial,
            trial_inicio=date.today() if trial else None,
            trial_fim=date.today() + timedelta(days=14) if trial else None,
        )

        user = User.objects.create_user(
            username=admin_user,
            email=admin_email,
            password=admin_senha,
            first_name=nome,
        )

        PerfilUsuario.objects.create(user=user, tenant=tenant)
        ConfiguracaoEmpresa(tenant=tenant, nome_empresa=nome, ativo=True).save()

        return redirect('admin_aurora:tenant_detalhe', tenant_id=tenant.pk)

    return render(request, 'admin_aurora/criar_tenant.html', {})


@superuser_required
def logs_view(request):
    """Logs do sistema. Somente superusers."""
    nivel = request.GET.get('nivel', 'ERROR')
    logs = LogSistema.all_tenants.filter(nivel=nivel).order_by('-data_criacao')[:100]
    return render(request, 'admin_aurora/logs.html', {
        'logs': logs,
        'nivel': nivel,
    })


@superuser_required
@require_POST
def api_toggle_tenant(request):
    """Ativa/desativa um tenant via API. Somente superusers."""
    tenant_id = request.POST.get('tenant_id')
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    tenant.ativo = not tenant.ativo
    tenant.save()
    return JsonResponse({'ok': True, 'ativo': tenant.ativo})


# ══════════════════════════════════════════════════════════════════════════════
# PLANOS
# ══════════════════════════════════════════════════════════════════════════════

@staff_required
def planos_view(request):
    """Lista todos os planos agrupados por módulo."""
    planos_comercial = Plano.objects.filter(modulo='comercial').prefetch_related('features')
    planos_marketing = Plano.objects.filter(modulo='marketing').prefetch_related('features')
    planos_cs = Plano.objects.filter(modulo='cs').prefetch_related('features')

    return render(request, 'admin_aurora/planos.html', {
        'planos_comercial': planos_comercial,
        'planos_marketing': planos_marketing,
        'planos_cs': planos_cs,
    })


@staff_required
def plano_detalhe_view(request, plano_id):
    """Detalhe e edição de um plano com suas features."""
    plano = get_object_or_404(Plano, pk=plano_id)
    features = plano.features.all().order_by('categoria', 'nome')
    categorias = dict(FeaturePlano.CATEGORIA_CHOICES)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'atualizar_plano':
            plano.nome = request.POST.get('nome', plano.nome)
            plano.descricao = request.POST.get('descricao', '')
            plano.preco_mensal = request.POST.get('preco_mensal', plano.preco_mensal)
            plano.preco_transacional = request.POST.get('preco_transacional', plano.preco_transacional)
            plano.unidade_transacional = request.POST.get('unidade_transacional', '')
            plano.destaque = request.POST.get('destaque') == 'on'
            plano.save()

        elif action == 'adicionar_feature':
            FeaturePlano.objects.create(
                plano=plano,
                nome=request.POST.get('feature_nome', ''),
                slug=request.POST.get('feature_slug', ''),
                categoria=request.POST.get('feature_categoria', 'core'),
                descricao=request.POST.get('feature_descricao', ''),
            )

        elif action == 'remover_feature':
            feature_id = request.POST.get('feature_id')
            FeaturePlano.objects.filter(pk=feature_id, plano=plano).delete()

        elif action == 'toggle_feature':
            feature_id = request.POST.get('feature_id')
            feature = FeaturePlano.objects.filter(pk=feature_id, plano=plano).first()
            if feature:
                feature.ativo = not feature.ativo
                feature.save()

        return redirect('admin_aurora:plano_detalhe', plano_id=plano.pk)

    # Agrupar features por categoria
    features_por_categoria = {}
    for f in features:
        cat = categorias.get(f.categoria, f.categoria)
        if cat not in features_por_categoria:
            features_por_categoria[cat] = []
        features_por_categoria[cat].append(f)

    tenants_usando = Tenant.objects.filter(
        **{f'plano_{plano.modulo}_ref': plano}
    ).count()

    return render(request, 'admin_aurora/plano_detalhe.html', {
        'plano': plano,
        'features_por_categoria': features_por_categoria,
        'categorias': categorias,
        'tenants_usando': tenants_usando,
    })
