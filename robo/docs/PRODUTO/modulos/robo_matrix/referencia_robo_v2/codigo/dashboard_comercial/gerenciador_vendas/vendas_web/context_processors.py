from .models import ConfiguracaoEmpresa


def empresa_context(request):
    """
    Context processor para disponibilizar configurações da empresa
    em todos os templates
    """
    # FORÇAR Megalink como nome da empresa
    return {
        'empresa_nome': 'Megalink',
        'empresa_logo': None,
        'empresa_cor_primaria': '#1F3D59',
        'empresa_cor_secundaria': '#2c5aa0',
    }
