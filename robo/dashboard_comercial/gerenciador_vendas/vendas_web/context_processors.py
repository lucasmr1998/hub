from .models import ConfiguracaoEmpresa


def empresa_context(request):
    """
    Context processor multi-tenant.
    Disponibiliza configurações da empresa e módulos contratados em todos os templates.
    """
    tenant = getattr(request, 'tenant', None)

    # Defaults
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
        return ctx

    # Módulos e planos do tenant
    ctx['modulo_comercial'] = tenant.modulo_comercial
    ctx['modulo_marketing'] = tenant.modulo_marketing
    ctx['modulo_cs'] = tenant.modulo_cs
    ctx['plano_comercial'] = tenant.plano_comercial
    ctx['plano_marketing'] = tenant.plano_marketing
    ctx['plano_cs'] = tenant.plano_cs
    ctx['em_trial'] = tenant.em_trial

    # Configuração visual da empresa
    config = ConfiguracaoEmpresa.all_tenants.filter(tenant=tenant, ativo=True).first()
    if config:
        ctx['empresa_nome'] = config.nome_empresa
        ctx['empresa_logo'] = config.logo_empresa.url if config.logo_empresa else None
        ctx['empresa_cor_primaria'] = config.cor_primaria
        ctx['empresa_cor_secundaria'] = config.cor_secundaria
    else:
        ctx['empresa_nome'] = tenant.nome
        ctx['setup_completo'] = False

    return ctx
