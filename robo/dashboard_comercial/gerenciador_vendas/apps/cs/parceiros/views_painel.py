from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
import json
from apps.cs.parceiros.models import Parceiro, CupomDesconto, ResgateCupom


def _get_parceiro(request):
    """Retorna o Parceiro vinculado ao usuário logado, ou None."""
    if not request.user.is_authenticated:
        return None
    try:
        return request.user.parceiro
    except Parceiro.DoesNotExist:
        return None


def painel_login(request):
    """Login do parceiro."""
    if request.user.is_authenticated:
        parceiro = _get_parceiro(request)
        if parceiro:
            return redirect('painel_home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            try:
                parceiro = user.parceiro
                auth_login(request, user)
                return redirect('painel_home')
            except Parceiro.DoesNotExist:
                messages.error(request, 'Este usuário não está vinculado a nenhum parceiro.')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')

    return render(request, 'parceiros/painel/login.html')


def painel_logout(request):
    auth_logout(request)
    return redirect('painel_login')


@login_required(login_url='/parceiro/login/')
def painel_home(request):
    """Dashboard do parceiro."""
    parceiro = _get_parceiro(request)
    if not parceiro:
        return redirect('painel_login')

    hoje = timezone.now().date()
    ultimos_7 = hoje - timedelta(days=7)
    anteriores_7 = ultimos_7 - timedelta(days=7)

    # Resgates do parceiro
    resgates_qs = ResgateCupom.objects.filter(cupom__parceiro=parceiro)

    total_resgates = resgates_qs.count()
    total_utilizados = resgates_qs.filter(status='utilizado').count()
    total_pendentes = resgates_qs.filter(status='resgatado').count()
    total_valor = resgates_qs.filter(valor_compra__isnull=False).aggregate(t=Sum('valor_compra'))['t'] or 0

    # Variação
    resgates_7d = resgates_qs.filter(data_resgate__date__gte=ultimos_7).count()
    resgates_ant = resgates_qs.filter(data_resgate__date__gte=anteriores_7, data_resgate__date__lt=ultimos_7).count()
    var = round(((resgates_7d - resgates_ant) / resgates_ant * 100), 1) if resgates_ant > 0 else 0

    # Evolução 7 dias
    evo = (
        resgates_qs.filter(data_resgate__date__gte=ultimos_7)
        .annotate(dia=TruncDate('data_resgate'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )
    evo_dict = {r['dia'].strftime('%d/%m'): r['total'] for r in evo if r['dia']}
    evo_labels = [(ultimos_7 + timedelta(days=i)).strftime('%d/%m') for i in range(7)]
    evo_data = [evo_dict.get(l, 0) for l in evo_labels]

    # Cupons ativos
    cupons_ativos = CupomDesconto.objects.filter(parceiro=parceiro, ativo=True).count()

    # Últimos resgates
    ultimos = resgates_qs.select_related('membro', 'cupom').order_by('-data_resgate')[:5]

    return render(request, 'parceiros/painel/home.html', {
        'parceiro': parceiro,
        'total_resgates': total_resgates,
        'total_utilizados': total_utilizados,
        'total_pendentes': total_pendentes,
        'total_valor': total_valor,
        'resgates_7d': resgates_7d,
        'var': var,
        'cupons_ativos': cupons_ativos,
        'chart_evo_labels': json.dumps(evo_labels),
        'chart_evo_data': json.dumps(evo_data),
        'ultimos': ultimos,
    })


@login_required(login_url='/parceiro/login/')
@transaction.atomic
def painel_cupons(request):
    """Cupons do parceiro."""
    parceiro = _get_parceiro(request)
    if not parceiro:
        return redirect('painel_login')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'solicitar':
            cupom = CupomDesconto.objects.create(
                parceiro=parceiro,
                titulo=request.POST.get('titulo', '').strip(),
                descricao=request.POST.get('descricao', '').strip(),
                codigo=request.POST.get('codigo', '').strip().upper(),
                tipo_desconto=request.POST.get('tipo_desconto', 'percentual'),
                valor_desconto=request.POST.get('valor_desconto', 0),
                modalidade='gratuito',
                custo_pontos=0,
                quantidade_total=int(request.POST.get('quantidade_total', 0) or 0),
                limite_por_membro=int(request.POST.get('limite_por_membro', 1) or 1),
                data_inicio=request.POST.get('data_inicio'),
                data_fim=request.POST.get('data_fim'),
                ativo=False,
                status_aprovacao='pendente',
            )
            if request.FILES.get('imagem'):
                cupom.imagem = request.FILES['imagem']
                cupom.save()
            messages.success(request, 'Solicitação enviada! Aguarde a aprovação do administrador.')
            return redirect('painel_cupons')

    cupons = CupomDesconto.objects.filter(parceiro=parceiro).annotate(
        total_resgates=Count('resgates'),
        total_utilizados=Count('resgates', filter=Q(resgates__status='utilizado')),
    ).order_by('-data_cadastro')

    return render(request, 'parceiros/painel/cupons.html', {
        'parceiro': parceiro,
        'cupons': cupons,
    })


@login_required(login_url='/parceiro/login/')
def painel_resgates(request):
    """Histórico de resgates do parceiro."""
    parceiro = _get_parceiro(request)
    if not parceiro:
        return redirect('painel_login')

    resgates = ResgateCupom.objects.filter(
        cupom__parceiro=parceiro
    ).select_related('membro', 'cupom').order_by('-data_resgate')

    busca = request.GET.get('busca', '').strip()
    status_filtro = request.GET.get('status', '')
    if busca:
        resgates = resgates.filter(
            Q(membro__nome__icontains=busca) | Q(codigo_unico__icontains=busca)
        )
    if status_filtro:
        resgates = resgates.filter(status=status_filtro)

    paginator = Paginator(resgates, 50)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'parceiros/painel/resgates.html', {
        'parceiro': parceiro,
        'resgates': page,
        'busca': busca,
        'status_filtro': status_filtro,
    })


@login_required(login_url='/parceiro/login/')
def painel_validar(request):
    """Validar cupom — versão painel do parceiro."""
    parceiro = _get_parceiro(request)
    if not parceiro:
        return redirect('painel_login')

    resgate = None
    erro = None
    sucesso = False

    if request.method == 'POST':
        action = request.POST.get('action')
        codigo = request.POST.get('codigo', '').strip().upper()

        if action == 'buscar':
            try:
                resgate = ResgateCupom.objects.select_related(
                    'membro', 'cupom', 'cupom__parceiro'
                ).get(codigo_unico=codigo, cupom__parceiro=parceiro)
            except ResgateCupom.DoesNotExist:
                erro = "Código não encontrado ou não pertence a este parceiro."

        elif action == 'confirmar':
            try:
                with transaction.atomic():
                    resgate = ResgateCupom.objects.select_for_update().select_related(
                        'membro', 'cupom', 'cupom__parceiro'
                    ).get(codigo_unico=codigo, cupom__parceiro=parceiro)

                    if resgate.status == 'utilizado':
                        erro = "Este cupom já foi utilizado."
                    elif resgate.status in ('expirado', 'cancelado'):
                        erro = f"Este cupom está {resgate.get_status_display().lower()}."
                    else:
                        valor_compra = request.POST.get('valor_compra', '').strip()
                        resgate.status = 'utilizado'
                        resgate.data_utilizacao = timezone.now()
                        if valor_compra:
                            resgate.valor_compra = valor_compra.replace(',', '.')
                        resgate.save(update_fields=['status', 'data_utilizacao', 'valor_compra'])
                        sucesso = True
            except ResgateCupom.DoesNotExist:
                erro = "Código não encontrado."

    return render(request, 'parceiros/painel/validar.html', {
        'parceiro': parceiro,
        'resgate': resgate,
        'erro': erro,
        'sucesso': sucesso,
    })
