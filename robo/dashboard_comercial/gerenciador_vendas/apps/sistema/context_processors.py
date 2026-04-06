from apps.sistema.models import ConfiguracaoEmpresa, PermissaoUsuario


def empresa_context(request):
    """
    Context processor multi-tenant.
    Disponibiliza configurações da empresa e módulos contratados em todos os templates.
    """
    tenant = getattr(request, 'tenant', None)

    ctx = {
        'empresa_nome': 'AuroraISP',
        'empresa_logo': None,
        'empresa_cor_primaria': '#1F3D59',
        'empresa_cor_secundaria': '#2c5aa0',
        'tenant': tenant,
        'modulo_comercial': False,
        'modulo_marketing': False,
        'modulo_cs': False,
        'plano_comercial': 'starter',
        'plano_marketing': 'starter',
        'plano_cs': 'starter',
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
    ctx['plano_comercial'] = tenant.plano_comercial
    ctx['plano_marketing'] = tenant.plano_marketing
    ctx['plano_cs'] = tenant.plano_cs
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
            # Cachear funcionalidades como set (do middleware ou direto)
            ctx['user_funcs'] = getattr(request, 'user_funcionalidades', None)
    else:
        ctx['perm'] = None
        ctx['is_superuser'] = False
        ctx['user_funcs'] = set()

    return ctx
