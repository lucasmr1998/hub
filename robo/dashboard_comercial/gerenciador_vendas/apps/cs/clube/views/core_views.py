from django.shortcuts import render, redirect
from django.db.models import Count, Q


def landing_clube(request):
    """Pagina publica do Clube — sem login."""
    from apps.cs.clube.models import LandingConfig, BannerClube, PremioRoleta, NivelClube, Cidade
    from apps.cs.parceiros.models import CategoriaParceiro, Parceiro, CupomDesconto

    config = LandingConfig.objects.first()
    banners = BannerClube.objects.filter(ativo=True).order_by('ordem')
    categorias = CategoriaParceiro.objects.filter(ativo=True).order_by('ordem')
    cidades = Cidade.objects.filter(ativo=True).order_by('nome')

    # Filtro por categoria
    categoria_slug = request.GET.get('categoria', '')
    parceiros_qs = Parceiro.objects.filter(ativo=True).select_related('categoria').annotate(
        total_cupons=Count('cupons', filter=Q(cupons__ativo=True, cupons__status_aprovacao='aprovado'))
    )
    if categoria_slug:
        parceiros_qs = parceiros_qs.filter(categoria__slug=categoria_slug)

    from django.core.paginator import Paginator

    # Cupons ativos
    cupons_qs = CupomDesconto.objects.filter(
        ativo=True, status_aprovacao='aprovado'
    ).select_related('parceiro').order_by('-data_cadastro')
    paginator_cupons = Paginator(cupons_qs, 8)
    pagina_cupons = request.GET.get('pagina_cupons', 1)
    cupons = paginator_cupons.get_page(pagina_cupons)

    # Premios (excluir "Nao foi dessa vez")
    premios = PremioRoleta.objects.exclude(
        nome__icontains='nao foi dessa vez'
    ).exclude(
        nome__icontains='não foi dessa vez'
    ).order_by('nome')

    # Niveis
    niveis = NivelClube.objects.all().order_by('ordem')

    # Filtros ativos
    busca = request.GET.get('busca', '').strip()
    cidade_id = request.GET.get('cidade', '')
    if busca:
        parceiros_qs = parceiros_qs.filter(nome__icontains=busca)
    if cidade_id:
        parceiros_qs = parceiros_qs.filter(cidades__id=cidade_id)

    paginator_parceiros = Paginator(parceiros_qs, 8)
    pagina = request.GET.get('pagina', 1)
    parceiros = paginator_parceiros.get_page(pagina)

    return render(request, 'clube/landing/clube.html', {
        'config': config,
        'banners': banners,
        'categorias': categorias,
        'cidades': cidades,
        'parceiros': parceiros,
        'cupons': cupons,
        'premios': premios,
        'niveis': niveis,
        'categoria_ativa': categoria_slug,
        'busca_ativa': busca,
        'cidade_ativa': cidade_id,
    })


def roleta_index(request):
    """
    Renders the plain HTML frontend without any context logic.
    All dynamic data is fetched via JS from /api/init-dados/
    """
    return render(request, 'clube/index_frontend.html')

def roleta_logout(request):
    """
    Limpa os dados de autenticação da sessão e redireciona para o início.
    """
    keys_to_clear = [
        'auth_membro_id', 'auth_membro_nome', 'auth_membro_cpf', 
        'otp_validado', 'sorteado_pos', 'nome_ganhador', 'premio_nome', 
        'saldo_atual', 'erro_sorteio'
    ]
    for key in keys_to_clear:
        request.session.pop(key, None)
    
    request.session.modified = True
    return redirect('roleta_index')
