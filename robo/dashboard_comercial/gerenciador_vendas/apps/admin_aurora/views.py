import re
from datetime import date, timedelta
from pathlib import Path

import markdown
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
from apps.sistema.utils import auditar

# Caminho base dos docs (relativo ao manage.py -> sobe até hub/)
DOCS_BASE = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / 'docs'
TAREFAS_PATH = DOCS_BASE / 'context' / 'tarefas'


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
@auditar('admin', 'gerenciar', 'tenant')
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
    integracao = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='hubsoft').first()

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
@auditar('admin', 'criar', 'tenant')
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
def monitoramento_view(request):
    """Painel de monitoramento do sistema."""
    from django.db import connection
    from django.db.models import Count
    from apps.comercial.leads.models import LeadProspecto
    from apps.comercial.atendimento.models import AtendimentoFluxo
    from apps.integracoes.models import LogIntegracao

    hoje = date.today()
    semana = hoje - timedelta(days=7)

    # Health check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = 'online'
    except Exception:
        db_status = 'offline'

    # Métricas de hoje
    leads_hoje = LeadProspecto.all_tenants.filter(data_cadastro__date=hoje).count()
    leads_semana = LeadProspecto.all_tenants.filter(data_cadastro__date__gte=semana).count()
    atendimentos_hoje = AtendimentoFluxo.all_tenants.filter(data_inicio__date=hoje).count()

    # Integrações
    logs_integracao = LogIntegracao.objects.order_by('-data_criacao')[:20]
    erros_integracao_24h = LogIntegracao.objects.filter(
        sucesso=False,
        data_criacao__gte=timezone.now() - timedelta(hours=24)
    ).count()
    sucesso_integracao_24h = LogIntegracao.objects.filter(
        sucesso=True,
        data_criacao__gte=timezone.now() - timedelta(hours=24)
    ).count()

    # Logs do sistema
    erros_24h = LogSistema.all_tenants.filter(
        nivel__in=['ERROR', 'CRITICAL'],
        data_criacao__gte=timezone.now() - timedelta(hours=24)
    ).count()
    warnings_24h = LogSistema.all_tenants.filter(
        nivel='WARNING',
        data_criacao__gte=timezone.now() - timedelta(hours=24)
    ).count()

    # Tenants
    tenants = Tenant.objects.all()
    tenants_ativos = tenants.filter(ativo=True).count()
    tenants_trial = tenants.filter(em_trial=True).count()

    # Últimos logs de erro
    ultimos_erros = LogSistema.all_tenants.filter(
        nivel__in=['ERROR', 'CRITICAL']
    ).order_by('-data_criacao')[:10]

    return render(request, 'admin_aurora/monitoramento.html', {
        'db_status': db_status,
        'leads_hoje': leads_hoje,
        'leads_semana': leads_semana,
        'atendimentos_hoje': atendimentos_hoje,
        'erros_integracao_24h': erros_integracao_24h,
        'sucesso_integracao_24h': sucesso_integracao_24h,
        'logs_integracao': logs_integracao,
        'erros_24h': erros_24h,
        'warnings_24h': warnings_24h,
        'tenants_ativos': tenants_ativos,
        'tenants_trial': tenants_trial,
        'ultimos_erros': ultimos_erros,
    })


@superuser_required
def logs_view(request):
    """Logs do sistema. Somente superusers."""
    from django.db.models import Count

    nivel = request.GET.get('nivel', '')
    modulo = request.GET.get('modulo', '')
    busca = request.GET.get('q', '')

    logs = LogSistema.all_tenants.all().order_by('-data_criacao')

    if nivel:
        logs = logs.filter(nivel=nivel)
    if modulo:
        logs = logs.filter(modulo__icontains=modulo)
    if busca:
        logs = logs.filter(mensagem__icontains=busca)

    # Counts per level
    level_counts = dict(
        LogSistema.all_tenants.values_list('nivel').annotate(c=Count('id')).values_list('nivel', 'c')
    )

    logs = logs[:200]

    return render(request, 'admin_aurora/logs.html', {
        'logs': logs,
        'nivel': nivel,
        'modulo': modulo,
        'busca': busca,
        'level_counts': level_counts,
    })


@superuser_required
@require_POST
@auditar('admin', 'toggle', 'tenant')
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
@auditar('admin', 'gerenciar', 'plano')
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


# ============================================================================
# DOCUMENTAÇÃO E PRODUTO
# ============================================================================

def _md_to_html(md_text):
    """Converte markdown para HTML."""
    return markdown.markdown(md_text, extensions=['tables', 'fenced_code', 'toc', 'nl2br'])


def _read_md(path):
    """Lê arquivo markdown com fallback."""
    try:
        return path.read_text(encoding='utf-8')
    except Exception:
        return ''


def _build_doc_tree(base_path, prefix=''):
    """Constrói árvore de documentos a partir de uma pasta."""
    items = []
    if not base_path.exists():
        return items

    dirs = sorted(p for p in base_path.iterdir() if p.is_dir() and not p.name.startswith('.'))
    files = sorted(p for p in base_path.iterdir() if p.is_file() and p.suffix == '.md' and p.name.upper() != 'TEMPLATE.MD')

    for d in dirs:
        children = _build_doc_tree(d, prefix=f'{prefix}/{d.name}' if prefix else d.name)
        if children:
            items.append({
                'type': 'dir',
                'name': d.name,
                'path': f'{prefix}/{d.name}' if prefix else d.name,
                'children': children,
                'count': sum(1 for c in children if c['type'] == 'file') + sum(c.get('count', 0) for c in children if c['type'] == 'dir'),
            })

    for f in files:
        name = f.stem.replace('-', ' ').replace('_', ' ')
        # Remove prefixo numérico (00-, 01-, etc)
        name = re.sub(r'^\d+\s*', '', name).strip()
        items.append({
            'type': 'file',
            'name': name or f.stem,
            'filename': f.name,
            'path': f'{prefix}/{f.name}' if prefix else f.name,
        })

    return items


@staff_required
def produto_view(request):
    """Status do Produto — renderiza 00-STATUS_PRODUTO.md"""
    status_path = DOCS_BASE / 'PRODUTO' / '00-STATUS_PRODUTO.md'
    md_content = _read_md(status_path)
    html_content = _md_to_html(md_content)

    return render(request, 'admin_aurora/produto.html', {
        'html_content': html_content,
    })


@staff_required
def docs_view(request):
    """Navegador de documentação — lê pastas de docs/"""
    tree = _build_doc_tree(DOCS_BASE)

    # Se um arquivo foi solicitado, renderizar
    file_path = request.GET.get('file', '')
    html_content = ''
    current_file = ''
    md_raw = ''

    if file_path:
        full_path = DOCS_BASE / file_path
        if full_path.exists() and full_path.suffix == '.md':
            md_raw = _read_md(full_path)
            html_content = _md_to_html(md_raw)
            current_file = file_path

    return render(request, 'admin_aurora/docs.html', {
        'tree': tree,
        'html_content': html_content,
        'current_file': current_file,
    })


@staff_required
def backlog_view(request):
    """Backlog de tarefas — lê docs/context/tarefas/"""
    pendentes = []
    finalizadas = []

    backlog_path = TAREFAS_PATH / 'backlog'
    final_path = TAREFAS_PATH / 'finalizadas'

    for folder, lista in [(backlog_path, pendentes), (final_path, finalizadas)]:
        if not folder.exists():
            continue
        for f in sorted(folder.iterdir()):
            if f.suffix != '.md' or f.name.upper() == 'TEMPLATE.MD':
                continue
            content = _read_md(f)
            # Extrair título e metadados do frontmatter
            titulo = f.stem.replace('-', ' ').replace('_', ' ')
            prioridade = ''
            responsavel = ''
            status = ''

            for line in content.split('\n')[:15]:
                if line.startswith('name:'):
                    titulo = line.split(':', 1)[1].strip().strip('"')
                elif 'prioridade' in line.lower() and ':' in line:
                    prioridade = line.split(':', 1)[1].strip().strip('"')
                elif 'responsavel' in line.lower() and ':' in line:
                    responsavel = line.split(':', 1)[1].strip().strip('"')
                elif 'status' in line.lower() and ':' in line and '**Status:**' in line:
                    status = line.split(':', 1)[1].strip().strip('*').strip()

            lista.append({
                'filename': f.name,
                'titulo': titulo,
                'prioridade': prioridade,
                'responsavel': responsavel,
                'status': status,
                'folder': folder.name,
                'path': f'context/tarefas/{folder.name}/{f.name}',
            })

    return render(request, 'admin_aurora/backlog.html', {
        'pendentes': pendentes,
        'finalizadas': finalizadas,
        'total_pendentes': len(pendentes),
        'total_finalizadas': len(finalizadas),
    })


@login_required
def config_recuperacao_senha_view(request):
    """Configuracao de recuperacao de senha (aurora-admin)."""
    from apps.sistema.models import ConfiguracaoRecuperacaoSenha
    from apps.integracoes.models import IntegracaoAPI

    config = ConfiguracaoRecuperacaoSenha.get_config()

    if request.method == 'POST':
        config.email_ativo = request.POST.get('email_ativo') == 'on'
        config.smtp_host = request.POST.get('smtp_host', '')
        config.smtp_porta = int(request.POST.get('smtp_porta', 587) or 587)
        config.smtp_usuario = request.POST.get('smtp_usuario', '')
        smtp_senha = request.POST.get('smtp_senha', '')
        if smtp_senha:
            config.smtp_senha = smtp_senha
        config.smtp_tls = request.POST.get('smtp_tls') == 'on'
        config.email_remetente = request.POST.get('email_remetente', '')

        config.whatsapp_ativo = request.POST.get('whatsapp_ativo') == 'on'
        integ_id = request.POST.get('whatsapp_integracao')
        config.whatsapp_integracao_id = integ_id if integ_id else None

        config.codigo_expiracao_minutos = int(request.POST.get('codigo_expiracao_minutos', 5) or 5)
        config.max_tentativas = int(request.POST.get('max_tentativas', 3) or 3)

        config.save()
        from django.contrib import messages
        messages.success(request, 'Configuracoes de recuperacao de senha salvas.')
        return redirect('admin_aurora:config_recuperacao_senha')

    integracoes = IntegracaoAPI.all_tenants.filter(tipo__in=['uazapi', 'evolution'], ativa=True)

    return render(request, 'admin_aurora/config_recuperacao_senha.html', {
        'config': config,
        'integracoes': integracoes,
    })
