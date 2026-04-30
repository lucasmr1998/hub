from apps.sistema.models import ConfiguracaoEmpresa, PermissaoUsuario


def empresa_context(request):
    """
    Context processor multi-tenant.
    Disponibiliza configurações da empresa e módulos contratados em todos os templates.
    """
    tenant = getattr(request, 'tenant', None)

    ctx = {
        'empresa_nome': 'Hubtrix',
        'empresa_logo': None,
        'empresa_cor_primaria': '#1F3D59',
        'empresa_cor_secundaria': '#2c5aa0',
        'tenant': tenant,
        'modulo_comercial': False,
        'modulo_marketing': False,
        'modulo_cs': False,
        'modulo_workspace': False,
        'plano_comercial': 'starter',
        'plano_marketing': 'starter',
        'plano_cs': 'starter',
        'plano_workspace': 'starter',
        'em_trial': False,
        'setup_completo': True,
    }

    if not tenant:
        # Mesmo sem tenant, precisa setar permissões para o template
        user = getattr(request, 'user', None)
        ctx['perm'] = None
        ctx['is_superuser'] = user.is_superuser if user and user.is_authenticated else False
        ctx['user_funcs'] = None if (user and user.is_authenticated) else set()
        return ctx

    ctx['modulo_comercial'] = tenant.modulo_comercial
    ctx['modulo_marketing'] = tenant.modulo_marketing
    ctx['modulo_cs'] = tenant.modulo_cs
    ctx['modulo_workspace'] = tenant.modulo_workspace
    ctx['plano_comercial'] = tenant.plano_comercial
    ctx['plano_marketing'] = tenant.plano_marketing
    ctx['plano_cs'] = tenant.plano_cs
    ctx['plano_workspace'] = tenant.plano_workspace
    ctx['em_trial'] = tenant.em_trial

    config = ConfiguracaoEmpresa.all_tenants.filter(tenant=tenant, ativo=True).first()
    if config:
        ctx['empresa_nome'] = config.nome_empresa
        ctx['empresa_logo'] = config.logo_empresa.url if config.logo_empresa else None
        ctx['empresa_cor_primaria'] = config.cor_primaria
        ctx['empresa_cor_secundaria'] = config.cor_secundaria
    else:
        ctx['empresa_nome'] = tenant.nome
        ctx['setup_completo'] = False

    # Token do widget para o tenant atual
    try:
        from apps.inbox.models import WidgetConfig
        wc = WidgetConfig.all_tenants.filter(tenant=tenant, ativo=True).first()
        ctx['widget_token'] = wc.token_publico if wc else ''
    except Exception:
        ctx['widget_token'] = ''

    # Permissões do usuário para a sidebar
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        if user.is_superuser:
            ctx['perm'] = None  # superuser = tudo liberado
            ctx['is_superuser'] = True
            ctx['user_funcs'] = None  # None = tudo liberado
        else:
            ctx['perm'] = PermissaoUsuario.get_for_user(user)
            ctx['is_superuser'] = False
            ctx['user_funcs'] = getattr(request, 'user_funcionalidades', None)

        # Status do agente (online/ausente/offline)
        try:
            from apps.inbox.models import PerfilAgenteInbox
            perfil_agente = PerfilAgenteInbox.objects.filter(user=user).first()
            ctx['agente_status'] = perfil_agente.status if perfil_agente else None
        except Exception:
            ctx['agente_status'] = None
    else:
        ctx['perm'] = None
        ctx['is_superuser'] = False
        ctx['user_funcs'] = set()
        ctx['agente_status'] = None

    ctx['modulo_atual'] = _detectar_modulo_atual(request)

    return ctx


def _detectar_modulo_atual(request):
    """
    Deduz o modulo ativo pela URL pra que a sidebar (layout_app) marque o item correto.
    Retorna uma das chaves: dashboard | comercial | marketing | atendimento | cs |
    relatorios | configuracoes | admin | None.
    """
    path = getattr(request, 'path', '') or ''
    url_name = ''
    app_name = ''
    try:
        if request.resolver_match:
            url_name = request.resolver_match.url_name or ''
            app_name = request.resolver_match.app_name or ''
    except Exception:
        pass

    if path.startswith('/aurora-admin/'):
        return 'admin'
    if path.startswith('/workspace/'):
        return 'workspace'
    if path.startswith('/cs/'):
        return 'cs'
    if path.startswith('/crm/') or path.startswith('/vendas/') or 'crm' in app_name:
        return 'comercial'
    if path.startswith('/inbox/') or path.startswith('/suporte/') or 'atendimento' in app_name:
        return 'atendimento'
    if path.startswith('/marketing/') or path.startswith('/leads/') or app_name == 'comercial_leads' or url_name in ('leads', 'campanhas_trafego', 'configuracoes_cadastro'):
        return 'marketing'
    if url_name.startswith('relatorio'):
        return 'relatorios'
    if '/configuracoes' in path or path.startswith('/perfil/'):
        return 'configuracoes'
    return 'dashboard'
