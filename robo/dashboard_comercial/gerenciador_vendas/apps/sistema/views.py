from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from apps.sistema.models import ConfiguracaoEmpresa


@login_required
def setup_inicial_view(request):
    """
    Tela de setup inicial para o primeiro login do tenant.
    Coleta: nome da empresa, logo, cores, credenciais HubSoft.
    """
    tenant = request.tenant
    if not tenant:
        return redirect('vendas_web:home')

    config = ConfiguracaoEmpresa.all_tenants.filter(tenant=tenant, ativo=True).first()

    if request.method == 'POST':
        nome = request.POST.get('nome_empresa', '').strip()
        cor_primaria = request.POST.get('cor_primaria', '#1F3D59')
        cor_secundaria = request.POST.get('cor_secundaria', '#2c5aa0')

        if not nome:
            return render(request, 'sistema/setup_inicial.html', {
                'erro': 'Nome da empresa é obrigatório.',
                'config': config,
            })

        if config:
            config.nome_empresa = nome
            config.cor_primaria = cor_primaria
            config.cor_secundaria = cor_secundaria
            if request.FILES.get('logo'):
                config.logo_empresa = request.FILES['logo']
            config.save()
        else:
            config = ConfiguracaoEmpresa(
                tenant=tenant,
                nome_empresa=nome,
                cor_primaria=cor_primaria,
                cor_secundaria=cor_secundaria,
                ativo=True,
            )
            if request.FILES.get('logo'):
                config.logo_empresa = request.FILES['logo']
            config.save()

        # Salvar credenciais HubSoft se fornecidas
        hubsoft_url = request.POST.get('hubsoft_url', '').strip()
        hubsoft_client_id = request.POST.get('hubsoft_client_id', '').strip()

        if hubsoft_url and hubsoft_client_id:
            from apps.integracoes.models import IntegracaoAPI
            IntegracaoAPI.objects.update_or_create(
                tenant=tenant,
                tipo='hubsoft',
                defaults={
                    'nome': f'HubSoft {tenant.nome}',
                    'base_url': hubsoft_url,
                    'client_id': hubsoft_client_id,
                    'client_secret': request.POST.get('hubsoft_client_secret', ''),
                    'username': request.POST.get('hubsoft_username', ''),
                    'password': request.POST.get('hubsoft_password', ''),
                    'grant_type': 'password',
                    'ativa': True,
                }
            )

        return redirect('vendas_web:dashboard1')

    return render(request, 'sistema/setup_inicial.html', {
        'config': config,
        'tenant': tenant,
    })
