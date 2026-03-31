from django.shortcuts import render, redirect
from django.db.models import Count, Q
from django.http import JsonResponse
from apps.cs.clube.models import MembroClube, RegraPontuacao, ExtratoPontuacao, NivelClube, RoletaConfig, RouletteAsset, Cidade
from apps.cs.parceiros.models import CupomDesconto, ResgateCupom
from apps.cs.parceiros.services import CupomService
from apps.cs.indicacoes.models import Indicacao, IndicacaoConfig


def _get_membro(request):
    """Retorna membro autenticado ou None."""
    membro_id = request.session.get('auth_membro_id')
    if not membro_id:
        return None
    try:
        return MembroClube.objects.get(id=membro_id)
    except MembroClube.DoesNotExist:
        return None


def membro_hub(request):
    """Tela principal do membro com 4 cards."""
    membro = _get_membro(request)
    if not membro:
        return redirect('roleta_index')

    # Contadores para badges nos cards
    cupons_count = len(CupomService.cupons_disponiveis(membro))
    indicacoes_count = Indicacao.objects.filter(membro_indicador=membro).count()

    return render(request, 'clube/membro/hub.html', {
        'membro': membro,
        'cupons_count': cupons_count,
        'indicacoes_count': indicacoes_count,
    })


def membro_jogar(request):
    """Página da roleta no padrão do hub do membro."""
    membro = _get_membro(request)
    if not membro:
        return redirect('roleta_index')
    return render(request, 'clube/membro/jogar.html', {
        'membro': membro,
    })


def membro_cupons(request):
    """Página de cupons do membro."""
    membro = _get_membro(request)
    if not membro:
        return redirect('roleta_index')

    from django.core.paginator import Paginator

    cupons = CupomService.cupons_disponiveis(membro)

    # Resgates do membro com paginação
    resgates_qs = ResgateCupom.objects.filter(membro=membro).select_related('cupom', 'cupom__parceiro').order_by('-data_resgate')
    paginator = Paginator(resgates_qs, 5)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'clube/membro/cupons.html', {
        'membro': membro,
        'cupons': cupons,
        'meus_resgates': page,
    })


def membro_indicar(request):
    """Página de indicações do membro."""
    membro = _get_membro(request)
    if not membro:
        return redirect('roleta_index')

    # Garantir código de indicação
    if not membro.codigo_indicacao:
        membro.save()
        membro.refresh_from_db()

    config, _ = IndicacaoConfig.objects.get_or_create(id=1)
    indicacoes_qs = Indicacao.objects.filter(membro_indicador=membro)
    stats = indicacoes_qs.aggregate(
        total=Count('id'),
        convertidas=Count('id', filter=Q(status='convertido')),
        pendentes=Count('id', filter=Q(status='pendente')),
    )
    indicacoes = indicacoes_qs.order_by('-data_indicacao')[:30]

    return render(request, 'clube/membro/indicar.html', {
        'membro': membro,
        'config': config,
        'indicacoes': indicacoes,
        'total': stats['total'],
        'convertidas': stats['convertidas'],
        'pendentes': stats['pendentes'],
    })


def membro_missoes(request):
    """Página de missões do membro."""
    membro = _get_membro(request)
    if not membro:
        return redirect('roleta_index')

    regras = RegraPontuacao.objects.filter(ativo=True, visivel_na_roleta=True)
    conclusoes_map = dict(
        ExtratoPontuacao.objects.filter(membro=membro, regra__in=regras)
        .values_list('regra_id')
        .annotate(cnt=Count('id'))
        .values_list('regra_id', 'cnt')
    )
    missoes = []
    for r in regras:
        conclusoes = conclusoes_map.get(r.id, 0)
        missoes.append({
            'nome': r.nome_exibicao,
            'pontos_saldo': r.pontos_saldo,
            'pontos_xp': r.pontos_xp,
            'limite': r.limite_por_membro,
            'concluidas': conclusoes,
            'disponivel': r.limite_por_membro == 0 or conclusoes < r.limite_por_membro,
        })

    total = len(missoes)
    concluidas = sum(1 for m in missoes if not m['disponivel'])

    return render(request, 'clube/membro/missoes.html', {
        'membro': membro,
        'missoes': missoes,
        'total': total,
        'concluidas': concluidas,
    })


def membro_perfil(request):
    """Página de perfil do membro."""
    membro = _get_membro(request)
    if not membro:
        return redirect('roleta_index')

    # Progressão de nível
    prox = membro.proximo_nivel
    if prox:
        nivel_anterior = NivelClube.objects.filter(xp_necessario__lte=membro.xp_total).order_by('-xp_necessario').first()
        xp_base = nivel_anterior.xp_necessario if nivel_anterior else 0
        xp_para_subir = prox.xp_necessario - xp_base
        xp_ganho = membro.xp_total - xp_base
        progresso = int((xp_ganho / xp_para_subir) * 100) if xp_para_subir > 0 else 100
        prox_xp = prox.xp_necessario
    else:
        progresso = 100
        prox_xp = membro.xp_total

    # Extrato recente
    extrato = ExtratoPontuacao.objects.filter(membro=membro).select_related('regra').order_by('-data_recebimento')[:20]

    # Missões — query única para conclusões
    regras = RegraPontuacao.objects.filter(ativo=True, visivel_na_roleta=True)
    conclusoes_map = dict(
        ExtratoPontuacao.objects.filter(membro=membro, regra__in=regras)
        .values_list('regra_id')
        .annotate(cnt=Count('id'))
        .values_list('regra_id', 'cnt')
    )
    missoes = []
    for r in regras:
        conclusoes = conclusoes_map.get(r.id, 0)
        missoes.append({
            'nome': r.nome_exibicao,
            'pontos_saldo': r.pontos_saldo,
            'pontos_xp': r.pontos_xp,
            'limite': r.limite_por_membro,
            'concluidas': conclusoes,
            'disponivel': r.limite_por_membro == 0 or conclusoes < r.limite_por_membro,
        })

    return render(request, 'clube/membro/perfil.html', {
        'membro': membro,
        'progresso': progresso,
        'prox_xp': prox_xp,
        'extrato': extrato,
        'missoes': missoes,
    })


def membro_faq(request):
    """Página de FAQ do membro."""
    membro = _get_membro(request)
    if not membro:
        return redirect('roleta_index')

    # from gestao.models import FAQCategoria, FAQItem  # TODO: migrar gestao para apps.cs
    from gestao.models import FAQCategoria, FAQItem
    from django.db.models import Prefetch

    categorias = FAQCategoria.objects.filter(ativo=True).prefetch_related(
        Prefetch('itens', queryset=FAQItem.objects.filter(ativo=True))
    )

    cat_slug = request.GET.get('cat')
    categoria_ativa = None
    if cat_slug:
        categoria_ativa = FAQCategoria.objects.filter(slug=cat_slug, ativo=True).first()

    return render(request, 'clube/membro/faq.html', {
        'membro': membro,
        'categorias': categorias,
        'categoria_ativa': categoria_ativa,
    })
