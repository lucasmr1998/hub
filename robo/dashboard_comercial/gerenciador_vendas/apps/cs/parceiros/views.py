from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, Sum, Case, When, IntegerField
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from apps.cs.parceiros.models import Parceiro, CupomDesconto, ResgateCupom
from apps.cs.clube.models import Cidade, NivelClube
from apps.sistema.validators import validate_image_upload


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_parceiros_home(request):
    """Dashboard principal do módulo Parceiros."""
    hoje = timezone.now().date()
    ultimos_7 = hoje - timedelta(days=7)
    anteriores_7 = ultimos_7 - timedelta(days=7)

    # KPIs
    total_parceiros = Parceiro.objects.filter(ativo=True).count()
    total_cupons = CupomDesconto.objects.filter(ativo=True).count()
    total_resgates = ResgateCupom.objects.count()
    total_utilizados = ResgateCupom.objects.filter(status='utilizado').count()

    # Variação 7 dias
    resgates_7d = ResgateCupom.objects.filter(data_resgate__date__gte=ultimos_7).count()
    resgates_ant = ResgateCupom.objects.filter(data_resgate__date__gte=anteriores_7, data_resgate__date__lt=ultimos_7).count()
    var_resgates = round(((resgates_7d - resgates_ant) / resgates_ant * 100), 1) if resgates_ant > 0 else 0

    # Valor em compras
    total_valor = ResgateCupom.objects.filter(
        valor_compra__isnull=False
    ).aggregate(t=Sum('valor_compra'))['t'] or 0

    # Evolução diária (últimos 7 dias)
    evo_resgates = (
        ResgateCupom.objects.filter(data_resgate__date__gte=ultimos_7)
        .annotate(dia=TruncDate('data_resgate'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )
    evo_dict = {r['dia'].strftime('%d/%m'): r['total'] for r in evo_resgates if r['dia']}
    import json
    evo_labels = [(ultimos_7 + timedelta(days=i)).strftime('%d/%m') for i in range(7)]
    evo_data = [evo_dict.get(l, 0) for l in evo_labels]

    # Últimos resgates
    ultimos_resgates = ResgateCupom.objects.select_related(
        'membro', 'cupom', 'cupom__parceiro'
    ).order_by('-data_resgate')[:5]

    # Top cupons
    top_cupons = (
        CupomDesconto.objects.filter(ativo=True)
        .annotate(total_resgates=Count('resgates'))
        .select_related('parceiro')
        .order_by('-total_resgates')[:5]
    )

    return render(request, 'parceiros/dashboard/home.html', {
        'total_parceiros': total_parceiros,
        'total_cupons': total_cupons,
        'total_resgates': total_resgates,
        'total_utilizados': total_utilizados,
        'var_resgates': var_resgates,
        'resgates_7d': resgates_7d,
        'total_valor': total_valor,
        'chart_evo_labels': json.dumps(evo_labels),
        'chart_evo_data': json.dumps(evo_data),
        'ultimos_resgates': ultimos_resgates,
        'top_cupons': top_cupons,
    })


@login_required(login_url='/roleta/dashboard/login/')
@transaction.atomic
def dashboard_parceiros(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar':
            try:
                if request.FILES.get('logo'):
                    validate_image_upload(request.FILES['logo'])
            except ValidationError as e:
                messages.error(request, e.message)
                return redirect('dashboard_parceiros')

            parceiro = Parceiro.objects.create(
                nome=request.POST.get('nome', '').strip(),
                descricao=request.POST.get('descricao', '').strip(),
                contato_nome=request.POST.get('contato_nome', '').strip(),
                contato_telefone=request.POST.get('contato_telefone', '').strip(),
                contato_email=request.POST.get('contato_email', '').strip(),
                ativo=request.POST.get('ativo') == 'on',
            )
            if request.FILES.get('logo'):
                parceiro.logo = request.FILES['logo']
                parceiro.save()
            cidades_ids = request.POST.getlist('cidades')
            if cidades_ids:
                parceiro.cidades.set(cidades_ids)
            messages.success(request, f'Parceiro "{parceiro.nome}" criado.')

        elif action == 'editar':
            parceiro_id = request.POST.get('parceiro_id')
            parceiro = get_object_or_404(Parceiro, id=parceiro_id)
            try:
                if request.FILES.get('logo'):
                    validate_image_upload(request.FILES['logo'])
            except ValidationError as e:
                messages.error(request, e.message)
                return redirect('dashboard_parceiros')

            parceiro.nome = request.POST.get('nome', '').strip()
            parceiro.descricao = request.POST.get('descricao', '').strip()
            parceiro.contato_nome = request.POST.get('contato_nome', '').strip()
            parceiro.contato_telefone = request.POST.get('contato_telefone', '').strip()
            parceiro.contato_email = request.POST.get('contato_email', '').strip()
            parceiro.ativo = request.POST.get('ativo') == 'on'
            if request.FILES.get('logo'):
                parceiro.logo = request.FILES['logo']
            parceiro.save()
            cidades_ids = request.POST.getlist('cidades')
            parceiro.cidades.set(cidades_ids)
            messages.success(request, f'Parceiro "{parceiro.nome}" atualizado.')

        elif action == 'excluir':
            parceiro_id = request.POST.get('parceiro_id')
            parceiro = get_object_or_404(Parceiro, id=parceiro_id)
            nome = parceiro.nome
            parceiro.delete()
            messages.success(request, f'Parceiro "{nome}" excluído.')

        return redirect('dashboard_parceiros')

    parceiros = Parceiro.objects.annotate(
        total_cupons=Count('cupons'),
        cupons_ativos=Count('cupons', filter=Q(cupons__ativo=True)),
    )

    busca = request.GET.get('busca', '').strip()
    if busca:
        parceiros = parceiros.filter(Q(nome__icontains=busca))

    cidades = Cidade.objects.filter(ativo=True)

    return render(request, 'parceiros/dashboard/parceiros.html', {
        'parceiros': parceiros,
        'cidades': cidades,
        'busca': busca,
    })


@login_required(login_url='/roleta/dashboard/login/')
@transaction.atomic
def dashboard_cupons(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action in ('criar', 'editar'):
            try:
                if request.FILES.get('imagem'):
                    validate_image_upload(request.FILES['imagem'])
            except ValidationError as e:
                messages.error(request, e.message)
                return redirect('dashboard_cupons')

            dados = {
                'titulo': request.POST.get('titulo', '').strip(),
                'descricao': request.POST.get('descricao', '').strip(),
                'codigo': request.POST.get('codigo', '').strip(),
                'tipo_desconto': request.POST.get('tipo_desconto', 'percentual'),
                'valor_desconto': request.POST.get('valor_desconto', 0),
                'modalidade': request.POST.get('modalidade', 'gratuito'),
                'custo_pontos': int(request.POST.get('custo_pontos', 0) or 0),
                'quantidade_total': int(request.POST.get('quantidade_total', 0) or 0),
                'limite_por_membro': int(request.POST.get('limite_por_membro', 1) or 1),
                'data_inicio': request.POST.get('data_inicio'),
                'data_fim': request.POST.get('data_fim'),
                'ativo': request.POST.get('ativo') == 'on',
            }

            parceiro_id = request.POST.get('parceiro_id')
            nivel_id = request.POST.get('nivel_minimo')

            if action == 'criar':
                cupom = CupomDesconto.objects.create(
                    parceiro_id=parceiro_id,
                    nivel_minimo_id=nivel_id if nivel_id else None,
                    **dados
                )
                if request.FILES.get('imagem'):
                    cupom.imagem = request.FILES['imagem']
                    cupom.save()
                cidades_ids = request.POST.getlist('cidades_permitidas')
                if cidades_ids:
                    cupom.cidades_permitidas.set(cidades_ids)
                messages.success(request, f'Cupom "{cupom.titulo}" criado.')

            elif action == 'editar':
                cupom_id = request.POST.get('cupom_id')
                cupom = get_object_or_404(CupomDesconto, id=cupom_id)
                for k, v in dados.items():
                    setattr(cupom, k, v)
                cupom.parceiro_id = parceiro_id
                cupom.nivel_minimo_id = nivel_id if nivel_id else None
                if request.FILES.get('imagem'):
                    cupom.imagem = request.FILES['imagem']
                cupom.save()
                cidades_ids = request.POST.getlist('cidades_permitidas')
                cupom.cidades_permitidas.set(cidades_ids)
                messages.success(request, f'Cupom "{cupom.titulo}" atualizado.')

        elif action == 'excluir':
            cupom_id = request.POST.get('cupom_id')
            cupom = get_object_or_404(CupomDesconto, id=cupom_id)
            titulo = cupom.titulo
            cupom.delete()
            messages.success(request, f'Cupom "{titulo}" excluído.')

        elif action == 'aprovar':
            cupom_id = request.POST.get('cupom_id')
            cupom = get_object_or_404(CupomDesconto, id=cupom_id)
            cupom.status_aprovacao = 'aprovado'
            cupom.ativo = True
            cupom.save(update_fields=['status_aprovacao', 'ativo'])
            messages.success(request, f'Cupom "{cupom.titulo}" aprovado e ativado.')

        elif action == 'rejeitar':
            cupom_id = request.POST.get('cupom_id')
            cupom = get_object_or_404(CupomDesconto, id=cupom_id)
            cupom.status_aprovacao = 'rejeitado'
            cupom.motivo_rejeicao = request.POST.get('motivo_rejeicao', '').strip()
            cupom.save(update_fields=['status_aprovacao', 'motivo_rejeicao'])
            messages.success(request, f'Cupom "{cupom.titulo}" rejeitado.')

        return redirect('dashboard_cupons')

    cupons = CupomDesconto.objects.select_related('parceiro', 'nivel_minimo').annotate(
        total_resgates=Count('resgates'),
    )

    busca = request.GET.get('busca', '').strip()
    parceiro_filtro = request.GET.get('parceiro', '')
    modalidade_filtro = request.GET.get('modalidade', '')
    aprovacao_filtro = request.GET.get('aprovacao', '')

    if busca:
        cupons = cupons.filter(Q(titulo__icontains=busca) | Q(codigo__icontains=busca))
    if parceiro_filtro:
        cupons = cupons.filter(parceiro_id=parceiro_filtro)
    if modalidade_filtro:
        cupons = cupons.filter(modalidade=modalidade_filtro)
    if aprovacao_filtro:
        cupons = cupons.filter(status_aprovacao=aprovacao_filtro)

    # Pendentes primeiro
    cupons = cupons.order_by(
        Case(
            When(status_aprovacao='pendente', then=0),
            default=1,
            output_field=IntegerField(),
        ),
        '-data_cadastro'
    )

    paginator = Paginator(cupons, 50)
    page = paginator.get_page(request.GET.get('page'))

    parceiros = Parceiro.objects.filter(ativo=True)
    cidades = Cidade.objects.filter(ativo=True)
    niveis = NivelClube.objects.all()

    return render(request, 'parceiros/dashboard/cupons.html', {
        'cupons': page,
        'parceiros': parceiros,
        'cidades': cidades,
        'niveis': niveis,
        'busca': busca,
        'parceiro_filtro': parceiro_filtro,
        'aprovacao_filtro': aprovacao_filtro,
        'modalidade_filtro': modalidade_filtro,
    })


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_cupom_detalhe(request, cupom_id):
    cupom = get_object_or_404(
        CupomDesconto.objects.select_related('parceiro', 'nivel_minimo'),
        id=cupom_id
    )
    resgates = ResgateCupom.objects.filter(cupom=cupom).select_related('membro')

    # KPIs
    total_resgates = resgates.count()
    total_utilizados = resgates.filter(status='utilizado').count()
    total_pendentes = resgates.filter(status='resgatado').count()
    total_pontos = resgates.aggregate(t=Sum('pontos_gastos'))['t'] or 0
    total_valor_compras = resgates.filter(valor_compra__isnull=False).aggregate(
        t=Sum('valor_compra')
    )['t'] or 0

    paginator = Paginator(resgates, 50)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'parceiros/dashboard/cupom_detalhe.html', {
        'cupom': cupom,
        'resgates': page,
        'total_resgates': total_resgates,
        'total_utilizados': total_utilizados,
        'total_pendentes': total_pendentes,
        'total_pontos': total_pontos,
        'total_valor_compras': total_valor_compras,
    })


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_cupons_resgates(request):
    resgates = ResgateCupom.objects.select_related('membro', 'cupom', 'cupom__parceiro')

    busca = request.GET.get('busca', '').strip()
    status_filtro = request.GET.get('status', '')

    if busca:
        resgates = resgates.filter(
            Q(membro__nome__icontains=busca) |
            Q(codigo_unico__icontains=busca) |
            Q(cupom__titulo__icontains=busca)
        )
    if status_filtro:
        resgates = resgates.filter(status=status_filtro)

    # KPIs
    total_resgates = resgates.count()
    total_utilizados = resgates.filter(status='utilizado').count()
    total_pontos_gastos = resgates.aggregate(total=Sum('pontos_gastos'))['total'] or 0

    paginator = Paginator(resgates, 50)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'parceiros/dashboard/cupons_resgates.html', {
        'resgates': page,
        'busca': busca,
        'status_filtro': status_filtro,
        'total_resgates': total_resgates,
        'total_utilizados': total_utilizados,
        'total_pontos_gastos': total_pontos_gastos,
    })


def validar_cupom(request):
    """Página pública para parceiros validarem/darem baixa em cupons."""
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
                ).get(codigo_unico=codigo)
            except ResgateCupom.DoesNotExist:
                erro = "Código não encontrado. Verifique e tente novamente."

        elif action == 'confirmar':
            try:
                with transaction.atomic():
                    resgate = ResgateCupom.objects.select_for_update().select_related(
                        'membro', 'cupom', 'cupom__parceiro'
                    ).get(codigo_unico=codigo)

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

    return render(request, 'parceiros/validar_cupom.html', {
        'resgate': resgate,
        'erro': erro,
        'sucesso': sucesso,
    })
