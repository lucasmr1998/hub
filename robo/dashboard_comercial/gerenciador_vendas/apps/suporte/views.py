import logging
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Ticket, ComentarioTicket, CategoriaTicket, HistoricoTicket
from apps.sistema.utils import auditar
from apps.sistema.decorators import user_tem_funcionalidade

logger = logging.getLogger(__name__)


def _auto_atribuir_ticket(ticket):
    """Auto-atribui ticket baseado na fila padrao da categoria."""
    fila = ticket.categoria.fila_padrao
    if not fila or not fila.ativo:
        return

    from apps.inbox.distribution import selecionar_agente
    agente = selecionar_agente(fila, ticket.tenant)

    if agente:
        ticket.atendente = agente
        ticket.status = 'em_andamento'
        ticket.save(update_fields=['atendente', 'status'])

        nome = agente.get_full_name() or agente.username
        HistoricoTicket.objects.create(
            ticket=ticket, tipo='atribuicao', usuario=None,
            campo='atendente', valor_anterior='Nenhum', valor_novo=nome,
            descricao=f'Auto-atribuido a {nome} (fila: {fila.nome})',
        )
        logger.info("Ticket #%s auto-atribuido a %s (fila: %s)", ticket.numero, nome, fila.nome)


@login_required
def dashboard_suporte(request):
    """Dashboard de suporte com metricas e relatorios."""
    from django.db.models import Avg
    from django.db.models.functions import TruncDate
    from datetime import timedelta

    tickets = Ticket.objects.all()
    agora = timezone.now()
    hoje = agora.date()
    periodo = int(request.GET.get('periodo', 30))
    data_inicio = agora - timedelta(days=periodo)
    tickets_periodo = tickets.filter(data_abertura__gte=data_inicio)

    # KPIs basicos
    abertos = tickets.filter(status='aberto').count()
    em_andamento = tickets.filter(status='em_andamento').count()
    aguardando = tickets.filter(status='aguardando_cliente').count()
    resolvidos_hoje = tickets.filter(status='resolvido', data_resolucao__date=hoje).count()

    # SLA breach count
    sla_breach = tickets.exclude(
        status__in=['resolvido', 'fechado']
    ).filter(sla_horas__isnull=False).extra(
        where=["EXTRACT(EPOCH FROM (%s - data_abertura)) / 3600 > sla_horas"],
        params=[agora]
    ).count() if tickets.exists() else 0

    # Metricas do periodo
    total_periodo = tickets_periodo.count()
    resolvidos_periodo = tickets_periodo.filter(status__in=['resolvido', 'fechado']).count()
    taxa_resolucao = (resolvidos_periodo / total_periodo * 100) if total_periodo else 0

    # Tempo medio resolucao
    resolvidos_qs = tickets_periodo.filter(data_resolucao__isnull=False)
    tempo_medio = None
    if resolvidos_qs.exists():
        tempos = [(t.data_resolucao - t.data_abertura).total_seconds() / 3600 for t in resolvidos_qs]
        tempo_medio = sum(tempos) / len(tempos)

    # Tempo medio primeira resposta
    com_resposta = tickets_periodo.filter(data_primeira_resposta__isnull=False)
    tempo_primeira_resp = None
    if com_resposta.exists():
        tempos_r = [(t.data_primeira_resposta - t.data_abertura).total_seconds() / 3600 for t in com_resposta]
        tempo_primeira_resp = sum(tempos_r) / len(tempos_r)

    # SLA compliance
    com_sla = tickets_periodo.filter(sla_horas__isnull=False)
    sla_total = com_sla.count()
    sla_cumpridos = sum(1 for t in com_sla if t.sla_cumprido)
    sla_compliance = (sla_cumpridos / sla_total * 100) if sla_total else None

    # CSAT
    com_csat = tickets_periodo.filter(csat_nota__isnull=False)
    csat_medio = com_csat.aggregate(media=Avg('csat_nota'))['media']
    csat_total = com_csat.count()

    # Por agente
    por_agente = tickets_periodo.filter(atendente__isnull=False).values(
        'atendente__first_name', 'atendente__last_name', 'atendente__username'
    ).annotate(
        total=Count('id'),
        resolvidos=Count('id', filter=Q(status__in=['resolvido', 'fechado'])),
    ).order_by('-total')

    # Por categoria
    por_categoria = tickets_periodo.values('categoria__nome').annotate(total=Count('id')).order_by('-total')

    # Por prioridade
    por_prioridade = tickets_periodo.values('prioridade').annotate(total=Count('id')).order_by('-total')

    # Ultimos tickets
    ultimos = tickets.order_by('-data_abertura')[:10]

    return render(request, 'suporte/dashboard_suporte.html', {
        'abertos': abertos,
        'em_andamento': em_andamento,
        'aguardando': aguardando,
        'resolvidos_hoje': resolvidos_hoje,
        'sla_breach': sla_breach,
        'periodo': periodo,
        'total_periodo': total_periodo,
        'resolvidos_periodo': resolvidos_periodo,
        'taxa_resolucao': taxa_resolucao,
        'tempo_medio': tempo_medio,
        'tempo_primeira_resp': tempo_primeira_resp,
        'sla_compliance': sla_compliance,
        'sla_total': sla_total,
        'csat_medio': csat_medio,
        'csat_total': csat_total,
        'por_agente': por_agente,
        'por_categoria': por_categoria,
        'por_prioridade': por_prioridade,
        'ultimos': ultimos,
    })


@login_required
def ticket_lista(request):
    """Lista de tickets com filtros e paginacao."""
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

    tickets = tickets.order_by('-data_abertura')

    # Paginacao
    paginator = Paginator(tickets, 50)
    page = request.GET.get('page', 1)
    tickets_page = paginator.get_page(page)

    categorias = CategoriaTicket.objects.filter(ativo=True)

    filter_fields = [
        {'type': 'select', 'label': 'Status', 'name': 'status', 'value': status,
         'options': [
             ('', 'Todos'),
             ('aberto', 'Aberto'),
             ('em_andamento', 'Em andamento'),
             ('aguardando_cliente', 'Aguardando cliente'),
             ('resolvido', 'Resolvido'),
             ('fechado', 'Fechado'),
         ]},
        {'type': 'select', 'label': 'Prioridade', 'name': 'prioridade', 'value': prioridade,
         'options': [
             ('', 'Todas'),
             ('baixa', 'Baixa'),
             ('normal', 'Normal'),
             ('alta', 'Alta'),
             ('urgente', 'Urgente'),
         ]},
        {'type': 'select', 'label': 'Categoria', 'name': 'categoria', 'value': categoria,
         'options': [('', 'Todas')] + [(str(c.pk), c.nome) for c in categorias]},
    ]
    active_filters_count = sum(1 for v in [status, prioridade, categoria] if v) + (1 if busca else 0)

    return render(request, 'suporte/ticket_lista.html', {
        'tickets': tickets_page,
        'categorias': categorias,
        'filter_fields': filter_fields,
        'active_filters_count': active_filters_count,
        'filtro_status': status,
        'filtro_prioridade': prioridade,
        'filtro_categoria': categoria,
        'busca': busca,
        'total': paginator.count,
    })


@login_required
@auditar('suporte', 'criar', 'ticket')
def ticket_criar(request):
    """Criar novo ticket."""
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        categoria_id = request.POST.get('categoria')
        prioridade = request.POST.get('prioridade', 'normal')

        if not titulo or not descricao:
            categorias = CategoriaTicket.objects.filter(ativo=True)
            return render(request, 'suporte/ticket_criar.html', {
                'categorias': categorias,
                'erro': 'Titulo e descricao sao obrigatorios.',
                'form': request.POST,
            })

        ticket = Ticket(
            titulo=titulo,
            descricao=descricao,
            prioridade=prioridade,
            solicitante=request.user,
            # FIX #2: tenant_cliente sempre e o tenant do usuario logado
            tenant_cliente=request.tenant,
        )
        if categoria_id:
            ticket.categoria_id = categoria_id
        ticket.save()

        HistoricoTicket.objects.create(
            ticket=ticket, tipo='criacao', usuario=request.user,
            descricao=f'Ticket criado: {titulo[:100]}',
        )

        # Auto-atribuicao: se categoria tem fila padrao, distribuir
        if ticket.categoria and ticket.categoria.fila_padrao:
            _auto_atribuir_ticket(ticket)

        return redirect('suporte:ticket_detalhe', pk=ticket.pk)

    categorias = CategoriaTicket.objects.filter(ativo=True)

    return render(request, 'suporte/ticket_criar.html', {
        'categorias': categorias,
    })


@login_required
@auditar('suporte', 'atualizar', 'ticket')
def ticket_detalhe(request, pk):
    """Detalhe do ticket com timeline de comentarios."""
    ticket = get_object_or_404(Ticket, pk=pk)

    # Filtrar comentarios internos: so visiveis para quem tem permissao
    if user_tem_funcionalidade(request, 'suporte.ver_interno'):
        comentarios = ticket.comentarios.select_related('autor').all()
    else:
        comentarios = ticket.comentarios.select_related('autor').filter(interno=False)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'comentar':
            mensagem = request.POST.get('mensagem', '').strip()
            interno = request.POST.get('interno') == 'on'
            if interno and not user_tem_funcionalidade(request, 'suporte.ver_interno'):
                interno = False
            if mensagem:
                ComentarioTicket.objects.create(
                    ticket=ticket,
                    autor=request.user,
                    mensagem=mensagem,
                    interno=interno,
                )
                HistoricoTicket.objects.create(
                    ticket=ticket, tipo='comentario', usuario=request.user,
                    descricao=f'Comentario {"interno" if interno else "publico"}: {mensagem[:100]}',
                )
                if not ticket.data_primeira_resposta and request.user != ticket.solicitante:
                    ticket.data_primeira_resposta = timezone.now()
                    ticket.save(update_fields=['data_primeira_resposta'])

        elif action == 'status' and user_tem_funcionalidade(request, 'suporte.gerenciar_tickets'):
            novo_status = request.POST.get('novo_status')
            if novo_status in dict(Ticket.STATUS_CHOICES):
                status_anterior = ticket.status
                ticket.status = novo_status
                if novo_status == 'resolvido' and not ticket.data_resolucao:
                    ticket.data_resolucao = timezone.now()
                elif novo_status == 'fechado' and not ticket.data_fechamento:
                    ticket.data_fechamento = timezone.now()
                ticket.save()
                HistoricoTicket.objects.create(
                    ticket=ticket, tipo='status', usuario=request.user,
                    campo='status', valor_anterior=status_anterior, valor_novo=novo_status,
                    descricao=f'Status alterado de {status_anterior} para {novo_status}',
                )

        elif action == 'atribuir' and user_tem_funcionalidade(request, 'suporte.gerenciar_tickets'):
            from django.contrib.auth.models import User
            atendente_id = request.POST.get('atendente_id')
            if atendente_id:
                atendente_anterior = ticket.atendente
                ticket.atendente_id = atendente_id
                if ticket.status == 'aberto':
                    ticket.status = 'em_andamento'
                ticket.save(update_fields=['atendente', 'status'])
                novo_atendente = User.objects.filter(pk=atendente_id).first()
                HistoricoTicket.objects.create(
                    ticket=ticket, tipo='atribuicao', usuario=request.user,
                    campo='atendente',
                    valor_anterior=str(atendente_anterior or 'Nenhum'),
                    valor_novo=str(novo_atendente.get_full_name() if novo_atendente else atendente_id),
                    descricao=f'Atribuido a {novo_atendente.get_full_name() if novo_atendente else atendente_id}',
                )

        return redirect('suporte:ticket_detalhe', pk=ticket.pk)

    # FIX #4: Atendentes filtrados por tenant
    from django.contrib.auth.models import User
    atendentes = User.objects.filter(
        is_active=True,
    ).order_by('first_name')

    from apps.inbox.models import RespostaRapida
    respostas_rapidas = RespostaRapida.objects.filter(ativo=True).order_by('categoria', 'titulo')
    historico = ticket.historico.select_related('usuario').all()[:50]

    return render(request, 'suporte/ticket_detalhe.html', {
        'ticket': ticket,
        'comentarios': comentarios,
        'atendentes': atendentes,
        'status_choices': Ticket.STATUS_CHOICES,
        'pode_gerenciar': user_tem_funcionalidade(request, 'suporte.gerenciar_tickets'),
        'respostas_rapidas': respostas_rapidas,
        'historico': historico,
    })


# ============================================================================
# BASE DE CONHECIMENTO
# ============================================================================

@login_required
def base_conhecimento(request):
    """Pagina principal da base de conhecimento."""
    from .models import CategoriaConhecimento, ArtigoConhecimento

    busca = request.GET.get('q', '').strip()
    categoria_slug = request.GET.get('categoria', '')

    categorias = CategoriaConhecimento.objects.filter(ativo=True).order_by('ordem')

    if busca:
        artigos = ArtigoConhecimento.objects.filter(
            publicado=True,
        ).filter(
            Q(titulo__icontains=busca) |
            Q(conteudo__icontains=busca) |
            Q(tags__icontains=busca) |
            Q(resumo__icontains=busca)
        ).select_related('categoria', 'autor')
    elif categoria_slug:
        artigos = ArtigoConhecimento.objects.filter(
            publicado=True, categoria__slug=categoria_slug,
        ).select_related('categoria', 'autor')
    else:
        artigos = ArtigoConhecimento.objects.filter(
            publicado=True,
        ).select_related('categoria', 'autor')

    # Paginacao
    paginator = Paginator(artigos, 30)
    page = request.GET.get('page', 1)
    artigos_page = paginator.get_page(page)

    destaques = ArtigoConhecimento.objects.filter(publicado=True, destaque=True).select_related('categoria')[:5]

    return render(request, 'suporte/base_conhecimento.html', {
        'categorias': categorias,
        'artigos': artigos_page,
        'destaques': destaques,
        'busca': busca,
        'categoria_ativa': categoria_slug,
        'total_artigos': paginator.count,
    })


@login_required
def artigo_conhecimento(request, slug):
    """Detalhe de um artigo da base de conhecimento."""
    from .models import ArtigoConhecimento

    artigo = get_object_or_404(ArtigoConhecimento, slug=slug, publicado=True)

    # Incrementar visualizacoes
    ArtigoConhecimento.objects.filter(pk=artigo.pk).update(visualizacoes=models.F('visualizacoes') + 1)

    # Artigos relacionados (mesma categoria)
    relacionados = ArtigoConhecimento.objects.filter(
        categoria=artigo.categoria, publicado=True,
    ).exclude(pk=artigo.pk).order_by('-atualizado_em')[:5]

    return render(request, 'suporte/artigo_conhecimento.html', {
        'artigo': artigo,
        'relacionados': relacionados,
    })


@login_required
def api_artigo_feedback(request, pk):
    """POST: Registrar feedback (util sim/nao)."""
    from .models import ArtigoConhecimento

    if request.method != 'POST':
        return JsonResponse({'error': 'Use POST'}, status=405)

    try:
        import json
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    voto = body.get('voto')  # 'sim' ou 'nao'
    if voto == 'sim':
        ArtigoConhecimento.objects.filter(pk=pk).update(util_sim=models.F('util_sim') + 1)
    elif voto == 'nao':
        ArtigoConhecimento.objects.filter(pk=pk).update(util_nao=models.F('util_nao') + 1)

    return JsonResponse({'success': True})


@login_required
@auditar('suporte', 'gerenciar', 'conhecimento')
def gerenciar_conhecimento(request):
    """CRUD de categorias e artigos da base de conhecimento."""
    from .models import CategoriaConhecimento, ArtigoConhecimento

    # FIX #3: Verificar permissao para gerenciar
    if not user_tem_funcionalidade(request, 'suporte.gerenciar_conhecimento'):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Sem permissao.')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar_categoria':
            from django.utils.text import slugify
            nome = request.POST.get('nome', '').strip()
            if nome:
                CategoriaConhecimento.objects.get_or_create(
                    tenant=request.tenant, slug=slugify(nome),
                    defaults={
                        'nome': nome,
                        'icone': request.POST.get('icone', 'fa-book'),
                        'cor_hex': request.POST.get('cor_hex', '#3b82f6'),
                    }
                )

        elif action == 'criar_artigo':
            from django.utils.text import slugify
            titulo = request.POST.get('titulo', '').strip()
            categoria_id = request.POST.get('categoria_id')
            if titulo and categoria_id:
                slug = slugify(titulo)
                # Evitar slug duplicado
                base_slug = slug
                counter = 1
                while ArtigoConhecimento.objects.filter(slug=slug).exists():
                    slug = f'{base_slug}-{counter}'
                    counter += 1
                ArtigoConhecimento.objects.create(
                    tenant=request.tenant,
                    categoria_id=categoria_id,
                    titulo=titulo,
                    slug=slug,
                    conteudo=request.POST.get('conteudo', ''),
                    resumo=request.POST.get('resumo', ''),
                    tags=request.POST.get('tags', ''),
                    autor=request.user,
                    publicado=request.POST.get('publicado') == 'on',
                    destaque=request.POST.get('destaque') == 'on',
                )

        elif action == 'editar_artigo':
            from django.utils.text import slugify
            artigo_id = request.POST.get('artigo_id')
            artigo = get_object_or_404(ArtigoConhecimento, pk=artigo_id)
            artigo.titulo = request.POST.get('titulo', artigo.titulo).strip()
            artigo.slug = slugify(artigo.titulo)
            artigo.conteudo = request.POST.get('conteudo', artigo.conteudo)
            artigo.resumo = request.POST.get('resumo', '')
            artigo.tags = request.POST.get('tags', '')
            artigo.categoria_id = request.POST.get('categoria_id', artigo.categoria_id)
            artigo.publicado = request.POST.get('publicado') == 'on'
            artigo.destaque = request.POST.get('destaque') == 'on'
            artigo.save()

        elif action == 'excluir_artigo':
            artigo_id = request.POST.get('artigo_id')
            ArtigoConhecimento.objects.filter(pk=artigo_id).delete()

        # FIX #7: Verificar se categoria tem artigos antes de deletar
        elif action == 'excluir_categoria':
            cat_id = request.POST.get('categoria_id')
            cat = CategoriaConhecimento.objects.filter(pk=cat_id).first()
            if cat:
                artigos_count = ArtigoConhecimento.objects.filter(categoria=cat).count()
                if artigos_count > 0:
                    from django.contrib import messages
                    messages.warning(request, f'Categoria "{cat.nome}" tem {artigos_count} artigo(s). Remova os artigos primeiro.')
                else:
                    cat.delete()

        return redirect('suporte:gerenciar_conhecimento')

    categorias = CategoriaConhecimento.objects.filter(ativo=True).order_by('ordem')
    artigos = ArtigoConhecimento.objects.all().select_related('categoria', 'autor').order_by('-atualizado_em')

    return render(request, 'suporte/gerenciar_conhecimento.html', {
        'categorias': categorias,
        'artigos': artigos,
    })


@login_required
def api_avaliar_ticket(request, pk):
    """POST: Avaliar ticket (CSAT)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Use POST'}, status=405)

    ticket = get_object_or_404(Ticket, pk=pk)

    import json
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    nota = body.get('nota')
    comentario = body.get('comentario', '')

    if not nota or int(nota) < 1 or int(nota) > 5:
        return JsonResponse({'error': 'Nota deve ser de 1 a 5'}, status=400)

    ticket.csat_nota = int(nota)
    ticket.csat_comentario = comentario
    ticket.csat_data = timezone.now()
    ticket.save(update_fields=['csat_nota', 'csat_comentario', 'csat_data'])

    HistoricoTicket.objects.create(
        ticket=ticket, tipo='status', usuario=request.user,
        descricao=f'Avaliacao CSAT: {nota}/5{" - " + comentario[:80] if comentario else ""}',
    )

    return JsonResponse({'ok': True})


@login_required
def api_acoes_massa(request):
    """POST: Acoes em massa nos tickets."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Use POST'}, status=405)

    if not user_tem_funcionalidade(request, 'suporte.gerenciar_tickets'):
        return JsonResponse({'error': 'Sem permissao'}, status=403)

    import json
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    ticket_ids = body.get('tickets', [])
    acao = body.get('acao', '')
    valor = body.get('valor', '')

    if not ticket_ids or not acao:
        return JsonResponse({'error': 'tickets e acao sao obrigatorios'}, status=400)

    tickets = Ticket.objects.filter(pk__in=ticket_ids)
    count = tickets.count()

    if acao == 'status' and valor in dict(Ticket.STATUS_CHOICES):
        for ticket in tickets:
            status_anterior = ticket.status
            ticket.status = valor
            if valor == 'resolvido' and not ticket.data_resolucao:
                ticket.data_resolucao = timezone.now()
            elif valor == 'fechado' and not ticket.data_fechamento:
                ticket.data_fechamento = timezone.now()
            ticket.save()
            HistoricoTicket.objects.create(
                ticket=ticket, tipo='status', usuario=request.user,
                campo='status', valor_anterior=status_anterior, valor_novo=valor,
                descricao=f'Status alterado em massa: {status_anterior} → {valor}',
            )

    elif acao == 'atribuir' and valor:
        from django.contrib.auth.models import User
        atendente = User.objects.filter(pk=valor, is_active=True).first()
        if atendente:
            nome = atendente.get_full_name() or atendente.username
            for ticket in tickets:
                anterior = str(ticket.atendente or 'Nenhum')
                ticket.atendente = atendente
                if ticket.status == 'aberto':
                    ticket.status = 'em_andamento'
                ticket.save(update_fields=['atendente', 'status'])
                HistoricoTicket.objects.create(
                    ticket=ticket, tipo='atribuicao', usuario=request.user,
                    campo='atendente', valor_anterior=anterior, valor_novo=nome,
                    descricao=f'Atribuido em massa a {nome}',
                )

    elif acao == 'prioridade' and valor in dict(Ticket.PRIORIDADE_CHOICES):
        for ticket in tickets:
            anterior = ticket.prioridade
            ticket.prioridade = valor
            ticket.save(update_fields=['prioridade'])
            HistoricoTicket.objects.create(
                ticket=ticket, tipo='prioridade', usuario=request.user,
                campo='prioridade', valor_anterior=anterior, valor_novo=valor,
                descricao=f'Prioridade alterada em massa: {anterior} → {valor}',
            )
    else:
        return JsonResponse({'error': f'Acao invalida: {acao}'}, status=400)

    return JsonResponse({'ok': True, 'count': count})


@login_required
def relatorios_suporte(request):
    """Relatorios avancados do suporte."""
    from django.db.models import Avg, Count, F
    from django.contrib.auth.models import User
    from datetime import timedelta

    periodo = request.GET.get('periodo', '30')
    dias = int(periodo) if periodo.isdigit() else 30
    data_inicio = timezone.now() - timedelta(days=dias)

    tickets_periodo = Ticket.objects.filter(data_abertura__gte=data_inicio)
    tickets_total = tickets_periodo.count()
    tickets_resolvidos = tickets_periodo.filter(status__in=['resolvido', 'fechado']).count()

    # Tempo medio de resolucao (em horas)
    resolvidos = tickets_periodo.filter(data_resolucao__isnull=False)
    tempo_medio = None
    if resolvidos.exists():
        tempos = []
        for t in resolvidos:
            delta = (t.data_resolucao - t.data_abertura).total_seconds() / 3600
            tempos.append(delta)
        tempo_medio = sum(tempos) / len(tempos) if tempos else None

    # Tempo medio primeira resposta (em horas)
    com_resposta = tickets_periodo.filter(data_primeira_resposta__isnull=False)
    tempo_primeira_resp = None
    if com_resposta.exists():
        tempos_resp = []
        for t in com_resposta:
            delta = (t.data_primeira_resposta - t.data_abertura).total_seconds() / 3600
            tempos_resp.append(delta)
        tempo_primeira_resp = sum(tempos_resp) / len(tempos_resp) if tempos_resp else None

    # SLA compliance
    com_sla = tickets_periodo.filter(sla_horas__isnull=False)
    sla_total = com_sla.count()
    sla_cumpridos = sum(1 for t in com_sla if t.sla_cumprido)
    sla_compliance = (sla_cumpridos / sla_total * 100) if sla_total else None

    # CSAT medio
    com_csat = tickets_periodo.filter(csat_nota__isnull=False)
    csat_medio = com_csat.aggregate(media=Avg('csat_nota'))['media']
    csat_total = com_csat.count()

    # Por agente
    por_agente = tickets_periodo.filter(
        atendente__isnull=False
    ).values(
        'atendente__id', 'atendente__first_name', 'atendente__last_name', 'atendente__username'
    ).annotate(
        total=Count('id'),
        resolvidos=Count('id', filter=Q(status__in=['resolvido', 'fechado'])),
    ).order_by('-total')

    # Por categoria
    por_categoria = tickets_periodo.values(
        'categoria__nome'
    ).annotate(total=Count('id')).order_by('-total')

    # Por prioridade
    por_prioridade = tickets_periodo.values('prioridade').annotate(total=Count('id')).order_by('-total')

    # Tendencia diaria (ultimos N dias)
    from django.db.models.functions import TruncDate
    tendencia = tickets_periodo.annotate(
        dia=TruncDate('data_abertura')
    ).values('dia').annotate(total=Count('id')).order_by('dia')

    return render(request, 'suporte/relatorios_suporte.html', {
        'periodo': dias,
        'tickets_total': tickets_total,
        'tickets_resolvidos': tickets_resolvidos,
        'taxa_resolucao': (tickets_resolvidos / tickets_total * 100) if tickets_total else 0,
        'tempo_medio': tempo_medio,
        'tempo_primeira_resp': tempo_primeira_resp,
        'sla_compliance': sla_compliance,
        'sla_total': sla_total,
        'csat_medio': csat_medio,
        'csat_total': csat_total,
        'por_agente': por_agente,
        'por_categoria': por_categoria,
        'por_prioridade': por_prioridade,
        'tendencia': list(tendencia),
    })


@login_required
def api_buscar_conhecimento(request):
    """GET: Busca rapida de artigos (para o Inbox)."""
    from .models import ArtigoConhecimento

    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse({'artigos': []})

    artigos = ArtigoConhecimento.objects.filter(
        publicado=True,
    ).filter(
        Q(titulo__icontains=q) |
        Q(conteudo__icontains=q) |
        Q(tags__icontains=q)
    ).values('id', 'titulo', 'resumo', 'categoria__nome', 'slug')[:10]

    return JsonResponse({'artigos': list(artigos)})


# ============================================================================
# PERGUNTAS SEM RESPOSTA (IA)
# ============================================================================

@login_required
def perguntas_sem_resposta(request):
    """Tela de gestão de perguntas sem resposta da IA."""
    from .models import PerguntaSemResposta

    status_filtro = request.GET.get('status', 'pendente')
    busca = request.GET.get('q', '').strip()

    qs = PerguntaSemResposta.objects.all()
    if status_filtro and status_filtro != 'todas':
        qs = qs.filter(status=status_filtro)
    if busca:
        qs = qs.filter(pergunta__icontains=busca)

    total_pendentes = PerguntaSemResposta.objects.filter(status='pendente').count()
    total_respondidas = PerguntaSemResposta.objects.filter(status='respondida').count()

    context = {
        'perguntas': qs[:100],
        'status_filtro': status_filtro,
        'busca': busca,
        'total_pendentes': total_pendentes,
        'total_respondidas': total_respondidas,
    }
    return render(request, 'suporte/perguntas_sem_resposta.html', context)


@login_required
def api_pergunta_resolver(request, pk):
    """Marca pergunta como respondida e vincula artigo (opcional)."""
    from .models import PerguntaSemResposta
    import json

    pergunta = get_object_or_404(PerguntaSemResposta, pk=pk)

    if request.method == 'POST':
        data = json.loads(request.body) if request.body else {}
        artigo_id = data.get('artigo_id')

        pergunta.status = 'respondida'
        pergunta.data_resposta = timezone.now()
        if artigo_id:
            pergunta.artigo_criado_id = artigo_id
        pergunta.save(update_fields=['status', 'data_resposta', 'artigo_criado_id'])

        return JsonResponse({'success': True, 'message': 'Pergunta marcada como respondida.'})

    return JsonResponse({'error': 'Método não permitido'}, status=405)


@login_required
def api_pergunta_ignorar(request, pk):
    """Marca pergunta como ignorada."""
    from .models import PerguntaSemResposta

    pergunta = get_object_or_404(PerguntaSemResposta, pk=pk)
    pergunta.status = 'ignorada'
    pergunta.save(update_fields=['status'])

    return JsonResponse({'success': True, 'message': 'Pergunta ignorada.'})
