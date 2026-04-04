"""
Views do Inbox: view principal + APIs internas (AJAX).
Todas protegidas por @login_required.
"""

import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    Conversa, RespostaRapida, EtiquetaConversa, NotaInternaConversa,
    EquipeInbox, MembroEquipeInbox, PerfilAgenteInbox,
    FilaInbox, RegraRoteamento, HorarioAtendimento, ConfiguracaoInbox, CanalInbox,
    CategoriaFAQ, ArtigoFAQ, WidgetConfig,
)
from .serializers import ConversaOutputSerializer, MensagemOutputSerializer
from . import services


# ── View principal ─────────────────────────────────────────────────────

@login_required
def inbox_view(request):
    agentes = User.objects.filter(is_active=True).order_by('first_name')
    etiquetas = EtiquetaConversa.objects.all()
    equipes = EquipeInbox.objects.filter(ativo=True)
    filas = FilaInbox.objects.filter(ativo=True).select_related('equipe')
    return render(request, 'inbox/inbox.html', {
        'agentes': agentes,
        'etiquetas': etiquetas,
        'equipes': equipes,
        'filas': filas,
    })


# ── APIs internas ──────────────────────────────────────────────────────

def _get_conversa(pk, request):
    return get_object_or_404(Conversa.objects.select_related(
        'canal', 'lead', 'agente', 'ticket', 'oportunidade',
    ), pk=pk)


@login_required
def api_conversas(request):
    """GET: Lista conversas com filtros."""
    qs = Conversa.objects.select_related('canal', 'agente', 'lead').prefetch_related('etiquetas')

    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    else:
        qs = qs.exclude(status='arquivada')

    agente_filter = request.GET.get('agente')
    if agente_filter == 'me':
        qs = qs.filter(agente=request.user)
    elif agente_filter == 'unassigned':
        qs = qs.filter(agente__isnull=True)
    elif agente_filter:
        qs = qs.filter(agente_id=agente_filter)

    canal_filter = request.GET.get('canal')
    if canal_filter:
        qs = qs.filter(canal__tipo=canal_filter)

    busca = request.GET.get('q', '').strip()
    if busca:
        from django.db.models import Q
        qs = qs.filter(
            Q(contato_nome__icontains=busca) |
            Q(contato_telefone__icontains=busca) |
            Q(numero__icontains=busca)
        )

    conversas = qs[:100]
    data = ConversaOutputSerializer(conversas, many=True).data
    return JsonResponse({'conversas': data})


@login_required
def api_conversa_detalhe(request, pk):
    """GET: Detalhe da conversa com contexto do lead."""
    conversa = _get_conversa(pk, request)

    # Marcar como lida
    services.marcar_mensagens_lidas(conversa)

    data = ConversaOutputSerializer(conversa).data

    # Contexto do lead
    if conversa.lead:
        lead = conversa.lead
        data['lead_info'] = {
            'id': lead.id,
            'nome': lead.nome_razaosocial,
            'telefone': lead.telefone,
            'email': lead.email or '',
            'origem': lead.origem or '',
            'score': lead.score_qualificacao,
            'status': lead.status_api,
            'data_criacao': lead.data_criacao.isoformat() if hasattr(lead, 'data_criacao') and lead.data_criacao else '',
        }

    # Oportunidade CRM
    if conversa.oportunidade:
        op = conversa.oportunidade
        data['oportunidade_info'] = {
            'id': op.id,
            'titulo': op.titulo,
            'estagio': op.estagio.nome if op.estagio else '',
            'valor_estimado': str(op.valor_estimado) if op.valor_estimado else '0',
            'responsavel': op.responsavel.get_full_name() if op.responsavel else '',
        }
    elif conversa.lead:
        # Tentar puxar oportunidade via lead
        try:
            op = conversa.lead.oportunidade_crm
            if op:
                data['oportunidade_info'] = {
                    'id': op.id,
                    'titulo': op.titulo,
                    'estagio': op.estagio.nome if op.estagio else '',
                    'valor_estimado': str(op.valor_estimado) if op.valor_estimado else '0',
                    'responsavel': op.responsavel.get_full_name() if op.responsavel else '',
                }
        except Exception:
            pass

    # Ticket vinculado
    if conversa.ticket:
        t = conversa.ticket
        data['ticket_info'] = {
            'id': t.id,
            'numero': t.numero,
            'titulo': t.titulo,
            'status': t.status,
        }

    # Notas internas
    notas = conversa.notas_internas.select_related('autor').all()[:20]
    data['notas'] = [
        {
            'id': n.id,
            'autor': n.autor.get_full_name() or n.autor.username,
            'conteudo': n.conteudo,
            'data': n.data_criacao.isoformat(),
        }
        for n in notas
    ]

    return JsonResponse(data)


@login_required
def api_mensagens(request, pk):
    """GET: Mensagens de uma conversa (paginado)."""
    conversa = _get_conversa(pk, request)
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 50))

    mensagens = conversa.mensagens.select_related('remetente_user').all()[offset:offset + limit]
    total = conversa.mensagens.count()

    data = MensagemOutputSerializer(mensagens, many=True).data
    return JsonResponse({
        'mensagens': data,
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@login_required
@require_http_methods(["POST"])
def api_enviar_mensagem(request, pk):
    """POST: Agente envia mensagem."""
    conversa = _get_conversa(pk, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    conteudo = body.get('conteudo', '').strip()
    if not conteudo:
        return JsonResponse({'error': 'Conteúdo obrigatório'}, status=400)

    mensagem = services.enviar_mensagem(
        conversa=conversa,
        conteudo=conteudo,
        user=request.user,
        tipo_conteudo=body.get('tipo_conteudo', 'texto'),
        arquivo_url=body.get('arquivo_url', ''),
        arquivo_nome=body.get('arquivo_nome', ''),
    )

    return JsonResponse({
        'success': True,
        'mensagem': MensagemOutputSerializer(mensagem).data,
    })


@login_required
@require_http_methods(["POST"])
def api_atribuir(request, pk):
    """POST: Atribuir conversa a um agente."""
    conversa = _get_conversa(pk, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    agente_id = body.get('agente_id')
    if not agente_id:
        return JsonResponse({'error': 'agente_id obrigatório'}, status=400)

    agente = get_object_or_404(User, pk=agente_id, is_active=True)
    services.atribuir_conversa(conversa, agente, atribuido_por=request.user)

    return JsonResponse({'success': True, 'agente_nome': agente.get_full_name() or agente.username})


@login_required
@require_http_methods(["POST"])
def api_resolver(request, pk):
    """POST: Resolver conversa."""
    conversa = _get_conversa(pk, request)
    services.resolver_conversa(conversa, request.user)
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_reabrir(request, pk):
    """POST: Reabrir conversa."""
    conversa = _get_conversa(pk, request)
    services.reabrir_conversa(conversa, request.user)
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_transferir(request, pk):
    """POST: Transferir conversa para agente, equipe ou fila."""
    conversa = _get_conversa(pk, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    para_agente = None
    para_equipe = None
    para_fila = None

    if body.get('para_agente_id'):
        para_agente = get_object_or_404(User, pk=body['para_agente_id'], is_active=True)
    elif body.get('para_fila_id'):
        para_fila = body['para_fila_id']
    elif body.get('para_equipe_id'):
        para_equipe = body['para_equipe_id']
    else:
        return JsonResponse({'error': 'Destino obrigatório (para_agente_id, para_equipe_id ou para_fila_id)'}, status=400)

    services.transferir_conversa(
        conversa=conversa,
        transferido_por=request.user,
        para_agente=para_agente,
        para_equipe=para_equipe,
        para_fila=para_fila,
        motivo=body.get('motivo', ''),
    )

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_criar_ticket(request, pk):
    """POST: Criar ticket de suporte a partir da conversa."""
    conversa = _get_conversa(pk, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    titulo = body.get('titulo', '').strip()
    if not titulo:
        return JsonResponse({'error': 'Título obrigatório'}, status=400)

    ticket = services.criar_ticket_de_conversa(
        conversa=conversa,
        titulo=titulo,
        user=request.user,
        categoria=body.get('categoria'),
    )

    return JsonResponse({
        'success': True,
        'ticket_id': ticket.id,
        'ticket_numero': ticket.numero,
    })


@login_required
@require_http_methods(["POST"])
def api_etiquetas_conversa(request, pk):
    """POST: Atualizar etiquetas da conversa."""
    conversa = _get_conversa(pk, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    etiqueta_ids = body.get('etiquetas', [])
    etiquetas = EtiquetaConversa.objects.filter(id__in=etiqueta_ids)
    conversa.etiquetas.set(etiquetas)

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_notas(request, pk):
    """POST: Adicionar nota interna à conversa."""
    conversa = _get_conversa(pk, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    conteudo = body.get('conteudo', '').strip()
    if not conteudo:
        return JsonResponse({'error': 'Conteúdo obrigatório'}, status=400)

    nota = NotaInternaConversa(
        tenant=conversa.tenant,
        conversa=conversa,
        autor=request.user,
        conteudo=conteudo,
    )
    nota.save()

    return JsonResponse({
        'success': True,
        'nota': {
            'id': nota.id,
            'autor': request.user.get_full_name() or request.user.username,
            'conteudo': nota.conteudo,
            'data': nota.data_criacao.isoformat(),
        },
    })


@login_required
def api_respostas_rapidas(request):
    """GET: Listar respostas rápidas."""
    respostas = RespostaRapida.objects.filter(ativo=True)
    data = [
        {
            'id': r.id,
            'titulo': r.titulo,
            'atalho': r.atalho,
            'conteudo': r.conteudo,
            'categoria': r.categoria,
        }
        for r in respostas
    ]
    return JsonResponse({'respostas': data})


@login_required
def api_etiquetas(request):
    """GET: Listar etiquetas disponíveis."""
    etiquetas = EtiquetaConversa.objects.all()
    data = [
        {'id': e.id, 'nome': e.nome, 'cor_hex': e.cor_hex}
        for e in etiquetas
    ]
    return JsonResponse({'etiquetas': data})


@login_required
@require_http_methods(["POST"])
def api_atualizar_status_agente(request):
    """POST: Atualizar status do agente (online/ausente/offline)."""
    from .models import PerfilAgenteInbox

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    novo_status = body.get('status')
    if novo_status not in ('online', 'ausente', 'offline'):
        return JsonResponse({'error': 'Status inválido'}, status=400)

    perfil, _ = PerfilAgenteInbox.objects.get_or_create(
        user=request.user,
        defaults={'tenant': getattr(request, 'tenant', None)}
    )
    perfil.status = novo_status
    perfil.save(update_fields=['status', 'ultimo_status_em'])

    return JsonResponse({
        'success': True,
        'status': novo_status,
        'capacidade_maxima': perfil.capacidade_maxima,
        'conversas_abertas': perfil.conversas_abertas_count,
    })


# ── Configurações ──────────────────────────────────────────────────

@login_required
def configuracoes_inbox(request):
    """Página de configurações do Inbox (equipes, filas, respostas, etc)."""
    from django.contrib import messages as django_messages

    if request.method == 'POST':
        action = request.POST.get('action', '')
        _processar_action_config(request, action, django_messages)

    # Horários como JSON para o template
    horarios_dict = {}
    for h in HorarioAtendimento.objects.all():
        horarios_dict[h.dia_semana] = {
            'ativo': h.ativo,
            'hora_inicio': h.hora_inicio.strftime('%H:%M') if h.hora_inicio else '',
            'hora_fim': h.hora_fim.strftime('%H:%M') if h.hora_fim else '',
        }

    widget_config = WidgetConfig.get_config()

    context = {
        'equipes': EquipeInbox.objects.prefetch_related('membros__user').filter(ativo=True),
        'filas': FilaInbox.objects.select_related('equipe').prefetch_related('regras'),
        'respostas': RespostaRapida.objects.all(),
        'etiquetas_list': EtiquetaConversa.objects.all(),
        'canais': CanalInbox.objects.all(),
        'horarios_json': json.dumps(horarios_dict),
        'config': ConfiguracaoInbox.get_config(),
        'categorias_faq': CategoriaFAQ.objects.prefetch_related('artigos').filter(ativo=True),
        'widget_config': widget_config,
        'usuarios': User.objects.filter(is_active=True).order_by('first_name'),
        'dias_semana': HorarioAtendimento.DIA_CHOICES,
        'modos_distribuicao': FilaInbox.MODO_DISTRIBUICAO_CHOICES,
        'page_title': 'Configurações do Inbox',
    }
    return render(request, 'inbox/configuracoes_inbox.html', context)


def _processar_action_config(request, action, django_messages):
    """Processa POST actions da página de configurações."""

    # ── Equipes ────────────────────────────────────────────────────
    if action == 'criar_equipe':
        nome = request.POST.get('nome', '').strip()
        if nome:
            EquipeInbox(
                nome=nome,
                descricao=request.POST.get('descricao', ''),
                cor_hex=request.POST.get('cor_hex', '#667eea'),
            ).save()
            django_messages.success(request, f'Equipe "{nome}" criada.')

    elif action == 'excluir_equipe':
        pk = request.POST.get('equipe_id')
        EquipeInbox.objects.filter(pk=pk).delete()
        django_messages.success(request, 'Equipe excluída.')

    elif action == 'adicionar_membro':
        equipe_id = request.POST.get('equipe_id')
        user_id = request.POST.get('user_id')
        cargo = request.POST.get('cargo', 'agente')
        equipe = EquipeInbox.objects.filter(pk=equipe_id).first()
        user = User.objects.filter(pk=user_id).first()
        if equipe and user:
            MembroEquipeInbox.objects.get_or_create(
                equipe=equipe, user=user,
                defaults={'cargo': cargo}
            )
            # Auto-criar perfil de agente
            PerfilAgenteInbox.objects.get_or_create(
                user=user,
                defaults={'tenant': equipe.tenant}
            )

    elif action == 'remover_membro':
        membro_id = request.POST.get('membro_id')
        MembroEquipeInbox.objects.filter(pk=membro_id).delete()

    # ── Filas ──────────────────────────────────────────────────────
    elif action == 'criar_fila':
        nome = request.POST.get('nome', '').strip()
        equipe_id = request.POST.get('equipe_id')
        equipe = EquipeInbox.objects.filter(pk=equipe_id).first()
        if nome and equipe:
            FilaInbox(
                nome=nome,
                descricao=request.POST.get('descricao', ''),
                equipe=equipe,
                modo_distribuicao=request.POST.get('modo_distribuicao', 'round_robin'),
                prioridade=int(request.POST.get('prioridade', 0)),
            ).save()
            django_messages.success(request, f'Fila "{nome}" criada.')

    elif action == 'excluir_fila':
        pk = request.POST.get('fila_id')
        FilaInbox.objects.filter(pk=pk).delete()
        django_messages.success(request, 'Fila excluída.')

    elif action == 'criar_regra':
        fila_id = request.POST.get('fila_id')
        fila = FilaInbox.objects.filter(pk=fila_id).first()
        if fila:
            RegraRoteamento(
                fila=fila,
                tipo=request.POST.get('tipo', 'canal'),
                canal_id=request.POST.get('canal_id') or None,
                etiqueta_id=request.POST.get('etiqueta_id') or None,
                horario_inicio=request.POST.get('horario_inicio') or None,
                horario_fim=request.POST.get('horario_fim') or None,
                dias_semana=request.POST.get('dias_semana', ''),
                prioridade=int(request.POST.get('prioridade', 0)),
            ).save()

    elif action == 'excluir_regra':
        pk = request.POST.get('regra_id')
        RegraRoteamento.objects.filter(pk=pk).delete()

    # ── Respostas Rápidas ──────────────────────────────────────────
    elif action == 'criar_resposta':
        titulo = request.POST.get('titulo', '').strip()
        if titulo:
            RespostaRapida(
                titulo=titulo,
                atalho=request.POST.get('atalho', ''),
                conteudo=request.POST.get('conteudo', ''),
                categoria=request.POST.get('categoria', ''),
                criado_por=request.user,
            ).save()

    elif action == 'excluir_resposta':
        pk = request.POST.get('resposta_id')
        RespostaRapida.objects.filter(pk=pk).delete()

    # ── Etiquetas ──────────────────────────────────────────────────
    elif action == 'criar_etiqueta':
        nome = request.POST.get('nome', '').strip()
        if nome:
            EtiquetaConversa(
                nome=nome,
                cor_hex=request.POST.get('cor_hex', '#667eea'),
                criado_por=request.user,
            ).save()

    elif action == 'excluir_etiqueta':
        pk = request.POST.get('etiqueta_id')
        EtiquetaConversa.objects.filter(pk=pk).delete()

    # ── Canais ─────────────────────────────────────────────────────
    elif action == 'editar_canal':
        canal_id = request.POST.get('canal_id')
        canal = CanalInbox.objects.filter(pk=canal_id).first()
        if canal:
            webhook_url = request.POST.get('webhook_envio_url', '').strip()
            config = canal.configuracao or {}
            config['webhook_envio_url'] = webhook_url
            canal.configuracao = config
            canal.save(update_fields=['configuracao'])
            django_messages.success(request, f'Canal "{canal.nome}" atualizado.')

    # ── Horário de Atendimento ─────────────────────────────────────
    elif action == 'salvar_horario':
        for dia in range(7):
            ativo = request.POST.get(f'dia_{dia}_ativo') == 'on'
            inicio = request.POST.get(f'dia_{dia}_inicio', '')
            fim = request.POST.get(f'dia_{dia}_fim', '')
            if inicio and fim:
                obj, _ = HorarioAtendimento.objects.get_or_create(
                    dia_semana=dia,
                    defaults={'hora_inicio': inicio, 'hora_fim': fim, 'ativo': ativo}
                )
                obj.hora_inicio = inicio
                obj.hora_fim = fim
                obj.ativo = ativo
                obj.save()
        django_messages.success(request, 'Horários salvos.')

    # ── Config Geral ───────────────────────────────────────────────
    elif action == 'salvar_config':
        config = ConfiguracaoInbox.get_config()
        config.mensagem_fora_horario = request.POST.get('mensagem_fora_horario', '')
        config.distribuicao_padrao = request.POST.get('distribuicao_padrao', 'round_robin')
        config.atribuir_ao_responder = request.POST.get('atribuir_ao_responder') == 'on'
        config.save()
        django_messages.success(request, 'Configurações salvas.')

    # ── FAQ ────────────────────────────────────────────────────────
    elif action == 'criar_categoria_faq':
        from django.utils.text import slugify
        nome = request.POST.get('nome', '').strip()
        if nome:
            CategoriaFAQ(
                nome=nome,
                slug=slugify(nome),
                icone=request.POST.get('icone', 'fa-circle-question'),
                cor=request.POST.get('cor', '#667eea'),
            ).save()

    elif action == 'excluir_categoria_faq':
        CategoriaFAQ.objects.filter(pk=request.POST.get('categoria_faq_id')).delete()

    elif action == 'criar_artigo_faq':
        cat_id = request.POST.get('categoria_faq_id')
        titulo = request.POST.get('titulo', '').strip()
        conteudo = request.POST.get('conteudo', '').strip()
        cat = CategoriaFAQ.objects.filter(pk=cat_id).first()
        if cat and titulo:
            ArtigoFAQ(categoria=cat, titulo=titulo, conteudo=conteudo).save()

    elif action == 'excluir_artigo_faq':
        ArtigoFAQ.objects.filter(pk=request.POST.get('artigo_faq_id')).delete()

    # ── Widget Config ──────────────────────────────────────────────
    elif action == 'salvar_widget_config':
        wc = WidgetConfig.get_config()
        wc.titulo = request.POST.get('titulo', wc.titulo)
        wc.mensagem_boas_vindas = request.POST.get('mensagem_boas_vindas', wc.mensagem_boas_vindas)
        wc.cor_primaria = request.POST.get('cor_primaria', wc.cor_primaria)
        wc.cor_header = request.POST.get('cor_header', wc.cor_header)
        wc.posicao = request.POST.get('posicao', wc.posicao)
        wc.mostrar_faq = request.POST.get('mostrar_faq') == 'on'
        wc.pedir_dados_antes = request.POST.get('pedir_dados_antes') == 'on'
        wc.ativo = request.POST.get('widget_ativo') == 'on'

        campos = []
        if request.POST.get('campo_nome') == 'on':
            campos.append('nome')
        if request.POST.get('campo_email') == 'on':
            campos.append('email')
        if request.POST.get('campo_telefone') == 'on':
            campos.append('telefone')
        wc.campos_obrigatorios = campos

        dominios_raw = request.POST.get('dominios_permitidos', '')
        wc.dominios_permitidos = [d.strip() for d in dominios_raw.split('\n') if d.strip()]

        wc.save()
        django_messages.success(request, 'Widget atualizado.')


# ── Dashboard de Métricas ──────────────────────────────────────────

@login_required
def dashboard_inbox(request):
    """Dashboard com KPIs e métricas do inbox."""
    from datetime import timedelta
    from django.db.models import Count, Avg

    hoje = timezone.now().date()
    conversas = Conversa.objects.all()

    # KPIs
    abertas = conversas.filter(status='aberta').count()
    pendentes = conversas.filter(status='pendente').count()
    resolvidas_hoje = conversas.filter(
        status='resolvida', data_resolucao__date=hoje
    ).count()

    avg_primeira_resposta = conversas.filter(
        tempo_primeira_resposta_seg__isnull=False
    ).aggregate(avg=Avg('tempo_primeira_resposta_seg'))['avg']

    total_conversas = conversas.exclude(status='arquivada').count()

    # Volume por canal
    por_canal = conversas.exclude(status='arquivada').values(
        'canal__tipo', 'canal__nome'
    ).annotate(total=Count('id')).order_by('-total')

    # Volume por equipe
    por_equipe = conversas.exclude(status='arquivada').filter(
        equipe__isnull=False
    ).values('equipe__nome', 'equipe__cor_hex').annotate(
        total=Count('id')
    ).order_by('-total')

    # Ranking agentes (últimos 30 dias)
    trinta_dias = hoje - timedelta(days=30)
    por_agente = conversas.filter(
        agente__isnull=False,
        status='resolvida',
        data_resolucao__date__gte=trinta_dias,
    ).values(
        'agente__first_name', 'agente__last_name', 'agente__username'
    ).annotate(
        total_resolvidas=Count('id'),
        avg_tempo=Avg('tempo_primeira_resposta_seg'),
    ).order_by('-total_resolvidas')[:15]

    # Volume últimos 30 dias (para gráfico)
    ultimos_30 = []
    for i in range(29, -1, -1):
        dia = hoje - timedelta(days=i)
        count = conversas.filter(data_abertura__date=dia).count()
        ultimos_30.append({'dia': dia.strftime('%d/%m'), 'count': count})

    context = {
        'abertas': abertas,
        'pendentes': pendentes,
        'resolvidas_hoje': resolvidas_hoje,
        'avg_primeira_resposta': avg_primeira_resposta,
        'total_conversas': total_conversas,
        'por_canal': por_canal,
        'por_equipe': por_equipe,
        'por_agente': por_agente,
        'ultimos_30_json': json.dumps(ultimos_30),
        'page_title': 'Dashboard do Inbox',
    }
    return render(request, 'inbox/dashboard_inbox.html', context)
