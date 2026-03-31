from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.http import Http404
from django.utils import timezone
from datetime import timedelta
import json
from apps.cs.indicacoes.models import Indicacao, IndicacaoConfig
from apps.cs.indicacoes.services import IndicacaoService
from apps.cs.clube.models import MembroClube


def _get_config():
    config, _ = IndicacaoConfig.objects.get_or_create(id=1)
    return config


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_indicacoes_home(request):
    """Dashboard principal do módulo Indicações."""
    hoje = timezone.now().date()
    ultimos_7 = hoje - timedelta(days=7)
    anteriores_7 = ultimos_7 - timedelta(days=7)

    # KPIs
    total = Indicacao.objects.count()
    pendentes = Indicacao.objects.filter(status='pendente').count()
    convertidos = Indicacao.objects.filter(status='convertido').count()
    taxa = round((convertidos / total * 100), 1) if total > 0 else 0

    # Variação 7 dias
    ind_7d = Indicacao.objects.filter(data_indicacao__date__gte=ultimos_7).count()
    ind_ant = Indicacao.objects.filter(data_indicacao__date__gte=anteriores_7, data_indicacao__date__lt=ultimos_7).count()
    var_ind = round(((ind_7d - ind_ant) / ind_ant * 100), 1) if ind_ant > 0 else 0

    # Evolução diária (últimos 7 dias)
    evo = (
        Indicacao.objects.filter(data_indicacao__date__gte=ultimos_7)
        .annotate(dia=TruncDate('data_indicacao'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )
    evo_dict = {r['dia'].strftime('%d/%m'): r['total'] for r in evo if r['dia']}
    evo_labels = [(ultimos_7 + timedelta(days=i)).strftime('%d/%m') for i in range(7)]
    evo_data = [evo_dict.get(l, 0) for l in evo_labels]

    # Top 5 embaixadores
    top_embaixadores = (
        MembroClube.objects
        .annotate(
            total_ind=Count('indicacoes_feitas'),
            ind_conv=Count('indicacoes_feitas', filter=Q(indicacoes_feitas__status='convertido')),
        )
        .filter(total_ind__gt=0)
        .order_by('-total_ind')[:5]
    )

    # Últimas indicações
    ultimas = Indicacao.objects.select_related('membro_indicador').order_by('-data_indicacao')[:5]

    return render(request, 'indicacoes/dashboard/home.html', {
        'total': total,
        'pendentes': pendentes,
        'convertidos': convertidos,
        'taxa': taxa,
        'ind_7d': ind_7d,
        'var_ind': var_ind,
        'chart_evo_labels': json.dumps(evo_labels),
        'chart_evo_data': json.dumps(evo_data),
        'top_embaixadores': top_embaixadores,
        'ultimas': ultimas,
    })


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_indicacoes(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        indicacao_id = request.POST.get('indicacao_id')

        if action == 'alterar_status':
            indicacao = get_object_or_404(Indicacao, id=indicacao_id)
            novo_status = request.POST.get('novo_status')

            if novo_status == 'convertido':
                sucesso, msg = IndicacaoService.confirmar_conversao(indicacao_id)
                if sucesso:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            else:
                indicacao.status = novo_status
                indicacao.save(update_fields=['status'])
                messages.success(request, f'Status atualizado para "{indicacao.get_status_display()}".')

        elif action == 'adicionar_obs':
            indicacao = get_object_or_404(Indicacao, id=indicacao_id)
            indicacao.observacoes = request.POST.get('observacoes', '')
            indicacao.save(update_fields=['observacoes'])
            messages.success(request, 'Observação salva.')

        return redirect('dashboard_indicacoes')

    indicacoes_qs = Indicacao.objects.select_related('membro_indicador')

    busca = request.GET.get('busca', '').strip()
    status_filtro = request.GET.get('status', '')

    if busca:
        indicacoes_qs = indicacoes_qs.filter(
            Q(nome_indicado__icontains=busca) |
            Q(telefone_indicado__icontains=busca) |
            Q(membro_indicador__nome__icontains=busca)
        )
    if status_filtro:
        indicacoes_qs = indicacoes_qs.filter(status=status_filtro)

    # KPIs
    total = indicacoes_qs.count()
    pendentes = indicacoes_qs.filter(status='pendente').count()
    convertidos = indicacoes_qs.filter(status='convertido').count()
    taxa_conversao = round((convertidos / total) * 100, 1) if total > 0 else 0

    # Top indicadores
    top_indicadores = MembroClube.objects.filter(
        indicacoes_feitas__isnull=False
    ).annotate(
        total_indicacoes=Count('indicacoes_feitas'),
        convertidas=Count('indicacoes_feitas', filter=Q(indicacoes_feitas__status='convertido')),
    ).order_by('-total_indicacoes')[:10]

    paginator = Paginator(indicacoes_qs, 50)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'indicacoes/dashboard/indicacoes.html', {
        'indicacoes': page,
        'busca': busca,
        'status_filtro': status_filtro,
        'total': total,
        'pendentes': pendentes,
        'convertidos': convertidos,
        'taxa_conversao': taxa_conversao,
        'top_indicadores': top_indicadores,
    })


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_indicacoes_membros(request):
    membros = MembroClube.objects.annotate(
        total_indicacoes=Count('indicacoes_feitas'),
        convertidas=Count('indicacoes_feitas', filter=Q(indicacoes_feitas__status='convertido')),
    ).order_by('-total_indicacoes', 'nome')

    busca = request.GET.get('busca', '').strip()
    if busca:
        membros = membros.filter(
            Q(nome__icontains=busca) | Q(cpf__icontains=busca) | Q(codigo_indicacao__icontains=busca)
        )

    # Gerar código para membros que não têm
    membros_sem_codigo = MembroClube.objects.filter(
        Q(codigo_indicacao__isnull=True) | Q(codigo_indicacao='')
    )
    for m in membros_sem_codigo:
        m.save()  # O save() auto-gera o codigo_indicacao

    paginator = Paginator(membros, 50)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'indicacoes/dashboard/indicacoes_membros.html', {
        'membros': page,
        'busca': busca,
    })


@login_required(login_url='/roleta/dashboard/login/')
def dashboard_indicacoes_visual(request):
    config = _get_config()

    if request.method == 'POST':
        config.titulo = request.POST.get('titulo', '').strip() or 'Megalink'
        config.subtitulo = request.POST.get('subtitulo', '').strip() or 'Clube de Fidelidade'
        config.texto_indicador = request.POST.get('texto_indicador', '').strip() or 'Você foi indicado por'
        config.texto_botao = request.POST.get('texto_botao', '').strip() or 'Enviar Indicação'
        config.texto_sucesso_titulo = request.POST.get('texto_sucesso_titulo', '').strip() or 'Indicação Registrada!'
        config.texto_sucesso_msg = request.POST.get('texto_sucesso_msg', '').strip() or config.texto_sucesso_msg
        config.cor_fundo = request.POST.get('cor_fundo', '#0f1b2d').strip()
        config.cor_botao = request.POST.get('cor_botao', '#0f1b2d').strip()
        config.mostrar_campo_cpf = request.POST.get('mostrar_campo_cpf') == 'on'
        config.mostrar_campo_cidade = request.POST.get('mostrar_campo_cidade') == 'on'

        if request.FILES.get('logo'):
            config.logo = request.FILES['logo']
        if request.FILES.get('imagem_fundo'):
            config.imagem_fundo = request.FILES['imagem_fundo']

        if request.POST.get('remover_logo') == '1':
            config.logo = None
        if request.POST.get('remover_fundo') == '1':
            config.imagem_fundo = None

        config.save()
        messages.success(request, 'Configurações visuais salvas.')
        return redirect('dashboard_indicacoes_visual')

    return render(request, 'indicacoes/dashboard/indicacoes_visual.html', {
        'config': config,
    })


def pagina_indicacao(request, codigo):
    """Página pública de indicação — acessível sem login."""
    try:
        membro = MembroClube.objects.get(codigo_indicacao=codigo)
    except MembroClube.DoesNotExist:
        raise Http404("Link de indicação inválido.")

    config = _get_config()
    sucesso = False
    erro = None

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        cpf = request.POST.get('cpf', '').strip()
        cidade = request.POST.get('cidade', '').strip()

        if not nome or not telefone:
            erro = "Nome e telefone são obrigatórios."
        else:
            ok, msg, indicacao = IndicacaoService.criar_indicacao(
                membro_indicador=membro,
                nome=nome,
                telefone=telefone,
                cpf=cpf,
                cidade=cidade,
            )
            if ok:
                sucesso = True
            else:
                erro = msg

    return render(request, 'indicacoes/indicar.html', {
        'membro': membro,
        'config': config,
        'sucesso': sucesso,
        'erro': erro,
    })
