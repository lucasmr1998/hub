import logging
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q

from .models import Ticket, ComentarioTicket, CategoriaTicket

logger = logging.getLogger(__name__)


@login_required
def dashboard_suporte(request):
    """Dashboard de suporte com métricas."""
    tickets = Ticket.objects.all()

    abertos = tickets.filter(status='aberto').count()
    em_andamento = tickets.filter(status='em_andamento').count()
    aguardando = tickets.filter(status='aguardando_cliente').count()
    resolvidos_hoje = tickets.filter(
        status='resolvido',
        data_resolucao__date=timezone.now().date()
    ).count()

    # SLA breach count
    sla_breach = 0
    for t in tickets.exclude(status__in=['resolvido', 'fechado']):
        if not t.sla_cumprido:
            sla_breach += 1

    # Tickets por categoria
    por_categoria = tickets.exclude(status='fechado').values(
        'categoria__nome'
    ).annotate(total=Count('id')).order_by('-total')

    # Últimos tickets
    ultimos = tickets.order_by('-data_abertura')[:10]

    return render(request, 'suporte/dashboard_suporte.html', {
        'abertos': abertos,
        'em_andamento': em_andamento,
        'aguardando': aguardando,
        'resolvidos_hoje': resolvidos_hoje,
        'sla_breach': sla_breach,
        'por_categoria': por_categoria,
        'ultimos': ultimos,
    })


@login_required
def ticket_lista(request):
    """Lista de tickets com filtros."""
    tickets = Ticket.objects.select_related('categoria', 'solicitante', 'atendente', 'tenant_cliente')

    status = request.GET.get('status', '')
    prioridade = request.GET.get('prioridade', '')
    categoria = request.GET.get('categoria', '')
    busca = request.GET.get('q', '')

    if status:
        tickets = tickets.filter(status=status)
    if prioridade:
        tickets = tickets.filter(prioridade=prioridade)
    if categoria:
        tickets = tickets.filter(categoria_id=categoria)
    if busca:
        tickets = tickets.filter(
            Q(titulo__icontains=busca) | Q(descricao__icontains=busca) | Q(numero__icontains=busca)
        )

    categorias = CategoriaTicket.objects.filter(ativo=True)

    return render(request, 'suporte/ticket_lista.html', {
        'tickets': tickets[:100],
        'categorias': categorias,
        'filtro_status': status,
        'filtro_prioridade': prioridade,
        'filtro_categoria': categoria,
        'busca': busca,
    })


@login_required
def ticket_criar(request):
    """Criar novo ticket."""
    if request.method == 'POST':
        from apps.sistema.models import Tenant

        titulo = request.POST.get('titulo', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_id = request.POST.get('categoria')
        prioridade = request.POST.get('prioridade', 'normal')
        tenant_cliente_id = request.POST.get('tenant_cliente')

        if not titulo or not descricao:
            categorias = CategoriaTicket.objects.filter(ativo=True)
            tenants = Tenant.objects.filter(ativo=True)
            return render(request, 'suporte/ticket_criar.html', {
                'categorias': categorias,
                'tenants': tenants,
                'erro': 'Título e descrição são obrigatórios.',
                'form': request.POST,
            })

        ticket = Ticket(
            titulo=titulo,
            descricao=descricao,
            prioridade=prioridade,
            solicitante=request.user,
        )
        if categoria_id:
            ticket.categoria_id = categoria_id
        if tenant_cliente_id:
            ticket.tenant_cliente_id = tenant_cliente_id
        ticket.save()

        return redirect('suporte:ticket_detalhe', pk=ticket.pk)

    from apps.sistema.models import Tenant
    categorias = CategoriaTicket.objects.filter(ativo=True)
    tenants = Tenant.objects.filter(ativo=True)

    return render(request, 'suporte/ticket_criar.html', {
        'categorias': categorias,
        'tenants': tenants,
    })


@login_required
def ticket_detalhe(request, pk):
    """Detalhe do ticket com timeline de comentários."""
    ticket = get_object_or_404(Ticket, pk=pk)

    # Filtrar comentários internos: só visíveis para staff
    if request.user.is_staff:
        comentarios = ticket.comentarios.select_related('autor').all()
    else:
        comentarios = ticket.comentarios.select_related('autor').filter(interno=False)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'comentar':
            mensagem = request.POST.get('mensagem', '').strip()
            interno = request.POST.get('interno') == 'on'
            if mensagem:
                ComentarioTicket.objects.create(
                    ticket=ticket,
                    autor=request.user,
                    mensagem=mensagem,
                    interno=interno,
                )
                # Auto-set primeira resposta
                if not ticket.data_primeira_resposta and request.user != ticket.solicitante:
                    ticket.data_primeira_resposta = timezone.now()
                    ticket.save(update_fields=['data_primeira_resposta'])

        elif action == 'status':
            novo_status = request.POST.get('novo_status')
            if novo_status in dict(Ticket.STATUS_CHOICES):
                ticket.status = novo_status
                if novo_status == 'resolvido' and not ticket.data_resolucao:
                    ticket.data_resolucao = timezone.now()
                elif novo_status == 'fechado' and not ticket.data_fechamento:
                    ticket.data_fechamento = timezone.now()
                ticket.save()

        elif action == 'atribuir':
            from django.contrib.auth.models import User
            atendente_id = request.POST.get('atendente_id')
            if atendente_id:
                ticket.atendente_id = atendente_id
                if ticket.status == 'aberto':
                    ticket.status = 'em_andamento'
                ticket.save(update_fields=['atendente', 'status'])

        return redirect('suporte:ticket_detalhe', pk=ticket.pk)

    from django.contrib.auth.models import User
    atendentes = User.objects.filter(is_staff=True, is_active=True).order_by('first_name')

    return render(request, 'suporte/ticket_detalhe.html', {
        'ticket': ticket,
        'comentarios': comentarios,
        'atendentes': atendentes,
        'status_choices': Ticket.STATUS_CHOICES,
    })
