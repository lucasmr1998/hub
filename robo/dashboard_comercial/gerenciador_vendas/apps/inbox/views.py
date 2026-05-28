"""
Views do Inbox: view principal + APIs internas (AJAX).
Todas protegidas por @login_required.
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    Conversa, Mensagem, RespostaRapida, EtiquetaConversa, NotaInternaConversa,
    EquipeInbox, MembroEquipeInbox, PerfilAgenteInbox,
    FilaInbox, RegraRoteamento, HorarioAtendimento, ConfiguracaoInbox, CanalInbox,
    CategoriaFAQ, ArtigoFAQ, WidgetConfig,
)
from .serializers import ConversaOutputSerializer, MensagemOutputSerializer
from . import services
from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.utils import auditar
from apps.integracoes.models import IntegracaoAPI

logger = logging.getLogger(__name__)


def _check_perm(request, codigo):
    if not user_tem_funcionalidade(request, codigo):
        return JsonResponse({'error': 'Sem permissão para esta ação'}, status=403)
    return None


def _get_fluxos_atendimento():
    from apps.comercial.atendimento.models import FluxoAtendimento
    return FluxoAtendimento.objects.filter(ativo=True, status='ativo').order_by('nome')


# ── View principal ─────────────────────────────────────────────────────

@login_required
def inbox_view(request):
    if not getattr(request, 'tenant', None):
        return HttpResponseForbidden('Tenant não identificado.')
    denied = _check_perm(request, 'inbox.ver_minhas')
    if denied: return denied
    agentes = User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name')
    etiquetas = EtiquetaConversa.all_tenants.filter(tenant=request.tenant)
    equipes = EquipeInbox.all_tenants.filter(tenant=request.tenant, ativo=True)
    filas = FilaInbox.all_tenants.filter(tenant=request.tenant, ativo=True).select_related('equipe')
    # Status dos agentes
    from .models import PerfilAgenteInbox
    agentes_status = {}
    for p in PerfilAgenteInbox.objects.filter(user__in=agentes):
        agentes_status[p.user_id] = p.status

    return render(request, 'inbox/inbox.html', {
        'agentes': agentes,
        'etiquetas': etiquetas,
        'equipes': equipes,
        'filas': filas,
        'user_is_admin': user_tem_funcionalidade(request, 'inbox.ver_todas'),
        'agentes_status_json': json.dumps(agentes_status),
    })


# ── APIs internas ──────────────────────────────────────────────────────

def _get_conversa(pk, request):
    return get_object_or_404(Conversa.objects.select_related(
        'canal', 'lead', 'agente', 'ticket', 'oportunidade',
    ), pk=pk)


@login_required
def api_conversas(request):
    """GET: Lista conversas com filtros."""
    from django.db.models import Q
    from .models import MembroEquipeInbox, FilaInbox

    qs = Conversa.objects.select_related('canal', 'agente', 'lead', 'fila').prefetch_related('etiquetas')

    # Filtro por modo de atendimento (bot/humano)
    modo_filter = request.GET.get('modo', '')
    if modo_filter == 'bot':
        qs = qs.filter(modo_atendimento='bot')
    elif modo_filter == 'humano':
        # "Humano" agrupa o que precisa de atendente: operador assumiu (humano)
        # + bot finalizou e a conversa caiu pra fila/vendedor (finalizado_bot).
        qs = qs.filter(modo_atendimento__in=['humano', 'finalizado_bot'])
    elif modo_filter == 'finalizado_bot':
        qs = qs.filter(modo_atendimento='finalizado_bot')
    # Se vazio, nao filtra por modo (ve tudo que a permissao permite)

    # Escopo de visibilidade baseado em funcionalidade
    is_admin = user_tem_funcionalidade(request, 'inbox.ver_todas')
    is_supervisor = user_tem_funcionalidade(request, 'inbox.ver_equipe')

    if not is_admin:
        # Nao-admins nao veem conversas do bot (exceto se filtro explicito)
        if modo_filter != 'bot':
            qs = qs.exclude(modo_atendimento='bot')

        if is_supervisor:
            # Supervisor: ve conversas de agentes da sua equipe + nao atribuidas da equipe
            membro = MembroEquipeInbox.objects.filter(user=request.user).first()
            if membro:
                equipe_users = MembroEquipeInbox.objects.filter(equipe=membro.equipe).values_list('user_id', flat=True)
                filas_equipe = FilaInbox.objects.filter(equipe=membro.equipe).values_list('id', flat=True)
                qs = qs.filter(
                    Q(agente_id__in=equipe_users) |
                    Q(agente__isnull=True, fila_id__in=filas_equipe)
                )
            else:
                qs = qs.filter(Q(agente=request.user) | Q(agente__isnull=True))
        else:
            # Agente: so as suas + nao atribuidas da fila da sua equipe (se manual)
            equipes_ids = MembroEquipeInbox.objects.filter(user=request.user).values_list('equipe_id', flat=True)
            filas_do_user = FilaInbox.objects.filter(equipe_id__in=equipes_ids).values_list('id', flat=True)
            qs = qs.filter(
                Q(agente=request.user) |
                Q(agente__isnull=True, fila_id__in=filas_do_user)
            )

    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    else:
        qs = qs.exclude(status__in=['arquivada', 'resolvida'])

    canal_filter = request.GET.get('canal')
    if canal_filter:
        qs = qs.filter(canal__tipo=canal_filter)

    fila_filter = request.GET.get('fila')
    if fila_filter:
        qs = qs.filter(fila_id=fila_filter)

    busca = request.GET.get('q', '').strip()
    if busca:
        qs = qs.filter(
            Q(contato_nome__icontains=busca) |
            Q(contato_telefone__icontains=busca) |
            Q(numero__icontains=busca)
        )

    # Contagens das abas (Minhas/Nao atribuidas/Todas) — calculadas sobre o
    # mesmo escopo de visibilidade/filtros, ANTES de aplicar o filtro de aba.
    # Assim "Minhas" = atribuidas a MIM (nao "qualquer agente"), batendo com
    # o que cada aba realmente lista quando clicada.
    counts = {
        'todas': qs.count(),
        'minhas': qs.filter(agente=request.user).count(),
        'nao_atribuidas': qs.filter(agente__isnull=True).count(),
    }

    agente_filter = request.GET.get('agente')
    if agente_filter == 'me':
        qs = qs.filter(agente=request.user)
    elif agente_filter == 'unassigned':
        qs = qs.filter(agente__isnull=True)
    elif agente_filter:
        qs = qs.filter(agente_id=agente_filter)

    ordem = request.GET.get('ordem', 'desc')
    if ordem == 'asc':
        qs = qs.order_by('ultima_mensagem_em')
    else:
        qs = qs.order_by('-ultima_mensagem_em')

    conversas = qs[:100]
    data = ConversaOutputSerializer(conversas, many=True).data
    return JsonResponse({'conversas': data, 'counts': counts})


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
    def _serialize_op(op):
        """Serializa oportunidade com info pra edicao inline no inbox."""
        estagios = []
        if op.pipeline_id:
            from apps.comercial.crm.models import PipelineEstagio
            for est in PipelineEstagio.objects.filter(pipeline=op.pipeline, ativo=True).order_by('ordem'):
                estagios.append({
                    'id': est.id,
                    'nome': est.nome,
                    'ordem': est.ordem,
                    'is_final_ganho': est.is_final_ganho,
                    'is_final_perdido': est.is_final_perdido,
                })
        tags = []
        try:
            for t in op.tags.all():
                tags.append({'nome': t.nome, 'cor_hex': getattr(t, 'cor_hex', '#94a3b8')})
        except Exception:
            pass
        return {
            'id': op.id,
            'titulo': op.titulo,
            'estagio': op.estagio.nome if op.estagio else '',
            'estagio_id': op.estagio_id if op.estagio_id else None,
            'pipeline_id': op.pipeline_id,
            'estagios_disponiveis': estagios,
            'tags': tags,
            'valor_estimado': str(op.valor_estimado) if op.valor_estimado else '0',
            'responsavel': op.responsavel.get_full_name() if op.responsavel else '',
        }

    if conversa.oportunidade:
        data['oportunidade_info'] = _serialize_op(conversa.oportunidade)
    elif conversa.lead:
        try:
            op = conversa.lead.oportunidade_crm
            if op:
                data['oportunidade_info'] = _serialize_op(op)
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

    # Conversas anteriores do mesmo contato
    if conversa.contato_telefone:
        anteriores = Conversa.all_tenants.filter(
            tenant=conversa.tenant,
            contato_telefone=conversa.contato_telefone,
        ).exclude(pk=conversa.pk).order_by('-data_abertura')[:10]

        data['conversas_anteriores'] = [
            {
                'id': c.id,
                'numero': c.numero,
                'status': c.status,
                'agente': c.agente.get_full_name() if c.agente else '',
                'data_abertura': c.data_abertura.isoformat() if c.data_abertura else '',
                'data_resolucao': c.data_resolucao.isoformat() if c.data_resolucao else '',
                'preview': c.ultima_mensagem_preview or '',
                'total_mensagens': c.mensagens.count(),
            }
            for c in anteriores
        ]
    else:
        data['conversas_anteriores'] = []

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
    """GET: Mensagens de uma conversa (paginado).

    Retorna as `limit` mais RECENTES (offset conta a partir do fim).
    Mensagens vem em ordem cronologica ASC pra renderizacao direta.
    """
    conversa = _get_conversa(pk, request)
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 50))

    qs = conversa.mensagens.select_related('remetente_user').order_by('-id')[offset:offset + limit]
    mensagens = list(reversed(list(qs)))
    total = conversa.mensagens.count()

    data = MensagemOutputSerializer(mensagens, many=True).data
    return JsonResponse({
        'mensagens': data,
        'total': total,
        'offset': offset,
        'has_more': (offset + limit) < total,
    })


@login_required
def api_midia(request, pk, msg_id):
    """
    Serve a midia (imagem/PDF/audio) de uma mensagem.

    LGPD: RG/CNH e comprovantes sao dado pessoal. O arquivo fica em storage
    privado (PrivateMidiaStorage, fora de /media/) e so e servido aqui, com
    login e escopo de tenant garantido por `_get_conversa`.
    """
    conversa = _get_conversa(pk, request)
    mensagem = get_object_or_404(Mensagem, pk=msg_id, conversa=conversa)
    if not mensagem.arquivo:
        raise Http404('Mensagem sem arquivo')
    import mimetypes
    ct = mimetypes.guess_type(mensagem.arquivo.name)[0] or 'application/octet-stream'
    resp = FileResponse(mensagem.arquivo.open('rb'), content_type=ct)
    nome = mensagem.arquivo_nome or mensagem.arquivo.name.rsplit('/', 1)[-1]
    resp['Content-Disposition'] = f'inline; filename="{nome}"'
    return resp


@login_required
@require_http_methods(["POST"])
def api_enviar_mensagem(request, pk):
    """POST: Agente envia mensagem."""
    denied = _check_perm(request, 'inbox.responder')
    if denied: return denied
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
@auditar('inbox', 'atribuir', 'conversa')
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
    denied = _check_perm(request, 'inbox.resolver')
    if denied: return denied
    conversa = _get_conversa(pk, request)
    services.resolver_conversa(conversa, request.user)
    from apps.sistema.utils import registrar_acao
    registrar_acao('inbox', 'resolver', 'conversa', conversa.pk,
                   f'Conversa resolvida: {conversa.contato_nome}', request=request)
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_reabrir(request, pk):
    """POST: Reabrir conversa."""
    conversa = _get_conversa(pk, request)
    services.reabrir_conversa(conversa, request.user)
    from apps.sistema.utils import registrar_acao
    registrar_acao('inbox', 'reabrir', 'conversa', conversa.pk,
                   f'Conversa reaberta: {conversa.contato_nome}', request=request)
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
@auditar('inbox', 'transferir', 'conversa')
def api_transferir(request, pk):
    """POST: Transferir conversa para agente, equipe ou fila."""
    denied = _check_perm(request, 'inbox.transferir_agente')
    if denied: return denied
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
@auditar('suporte', 'criar', 'ticket')
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
def api_atualizar_conversa(request, pk):
    """POST: Atualizar campos da conversa (equipe, prioridade, etiquetas)."""
    conversa = _get_conversa(pk, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    campos_update = []

    if 'prioridade' in body:
        conversa.prioridade = body['prioridade']
        campos_update.append('prioridade')

    if 'equipe_id' in body:
        equipe_id = body['equipe_id']
        if equipe_id:
            conversa.equipe_id = equipe_id
        else:
            conversa.equipe = None
        campos_update.append('equipe_id')

    if campos_update:
        conversa.save(update_fields=campos_update)

    if 'etiquetas' in body:
        etiqueta_ids = body['etiquetas']
        etiquetas = EtiquetaConversa.objects.filter(id__in=etiqueta_ids)
        conversa.etiquetas.set(etiquetas)

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def api_etiquetas_conversa(request, pk):
    """POST: Atualizar etiquetas da conversa (legacy)."""
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
    """
    GET: Listar respostas rápidas.

    Query params opcionais:
      ?conversa=<id> — se informado, retorna também `conteudo_renderizado`
                       com variáveis substituídas pelos dados da conversa.

    Variáveis suportadas em `conteudo`:
      {{nome_cliente}}, {{primeiro_nome}}, {{telefone}}, {{email}},
      {{atendente}}, {{primeiro_nome_atendente}}, {{empresa}}.
    """
    respostas = RespostaRapida.objects.filter(ativo=True)

    conversa = None
    conversa_id = request.GET.get('conversa')
    if conversa_id:
        try:
            conversa = Conversa.objects.select_related('lead', 'agente').filter(pk=conversa_id).first()
        except Exception:
            conversa = None

    data = []
    for r in respostas:
        item = {
            'id': r.id,
            'titulo': r.titulo,
            'atalho': r.atalho,
            'conteudo': r.conteudo,
            'categoria': r.categoria,
        }
        if conversa:
            item['conteudo_renderizado'] = renderizar_resposta(r.conteudo, conversa, request.user)
        data.append(item)

    return JsonResponse({
        'respostas': data,
        'variaveis_disponiveis': [
            {'tag': '{{nome_cliente}}', 'descricao': 'Nome completo do cliente / contato'},
            {'tag': '{{primeiro_nome}}', 'descricao': 'Primeiro nome do cliente'},
            {'tag': '{{telefone}}', 'descricao': 'Telefone do cliente'},
            {'tag': '{{email}}', 'descricao': 'E-mail do cliente'},
            {'tag': '{{atendente}}', 'descricao': 'Nome do atendente que está respondendo'},
            {'tag': '{{primeiro_nome_atendente}}', 'descricao': 'Primeiro nome do atendente'},
            {'tag': '{{empresa}}', 'descricao': 'Nome da empresa do cliente (se houver)'},
        ],
    })


@login_required
@require_http_methods(["GET", "POST"])
def api_resumir_conversa(request, conversa_id):
    """
    Gera resumo IA das últimas N mensagens da conversa.
    GET: retorna do cache se houver, senão gera.
    POST: força regenerar (ignora cache).
    Cache: 1h por conversa.
    """
    from django.core.cache import cache
    from apps.integracoes.models import IntegracaoAPI
    import requests as http_requests

    try:
        conversa = Conversa.objects.select_related('tenant', 'lead').get(pk=conversa_id)
    except Conversa.DoesNotExist:
        return JsonResponse({'error': 'Conversa não encontrada'}, status=404)

    cache_key = f'resumo_conversa_{conversa_id}'
    if request.method == 'GET':
        cached = cache.get(cache_key)
        if cached:
            return JsonResponse({'resumo': cached, 'from_cache': True})

    # Pega últimas 50 mensagens
    mensagens = list(
        Mensagem.objects.filter(conversa=conversa)
        .order_by('-criado_em')[:50]
    )
    mensagens.reverse()

    if not mensagens:
        return JsonResponse({'error': 'Conversa sem mensagens'}, status=400)

    # Monta transcript
    linhas = []
    for m in mensagens:
        remetente = (
            'Cliente' if m.remetente_tipo == 'cliente'
            else 'Bot' if m.remetente_tipo == 'bot'
            else 'Atendente'
        )
        conteudo = (m.conteudo or '')[:500]  # truncar pra evitar prompt muito longo
        linhas.append(f"[{remetente}] {conteudo}")
    transcript = '\n'.join(linhas)

    # Busca integração de IA do tenant
    integracao = IntegracaoAPI.all_tenants.filter(
        tenant=conversa.tenant,
        tipo__in=['openai', 'anthropic', 'groq'],
        ativa=True,
    ).first()

    if not integracao:
        return JsonResponse({
            'error': 'Nenhuma integração de IA ativa pra este tenant'
        }, status=503)

    api_key = (
        integracao.api_key
        or integracao.configuracoes_extras.get('api_key', '')
        or integracao.access_token
        or ''
    )
    modelo = integracao.configuracoes_extras.get('modelo', 'gpt-4o-mini')

    if integracao.tipo == 'openai':
        url = 'https://api.openai.com/v1/chat/completions'
    elif integracao.tipo == 'groq':
        url = 'https://api.groq.com/openai/v1/chat/completions'
    else:
        url = integracao.base_url

    cliente_nome = (
        (conversa.lead.nome_razaosocial if conversa.lead else None)
        or conversa.contato_nome
        or 'cliente'
    )

    system_prompt = (
        "Você é um assistente que resume conversas de atendimento ao cliente "
        "de provedor de internet (ISP). Seja extremamente conciso. "
        "Português brasileiro, tom profissional."
    )

    user_prompt = (
        f"Resuma a conversa abaixo (cliente: {cliente_nome}) em até 5 bullets curtos, focando em:\n"
        f"1. Motivo do contato\n"
        f"2. Dados confirmados (plano, endereço, viabilidade, etc)\n"
        f"3. Decisões/acordos firmados\n"
        f"4. Próximos passos pendentes\n"
        f"5. Status atual (se aplicável)\n\n"
        f"Formato: bullets com '-' iniciando cada um. Sem cabeçalho. Sem numerais.\n\n"
        f"--- TRANSCRIPT ---\n{transcript}"
    )

    try:
        resp = http_requests.post(
            url,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': modelo,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.2,
                'max_tokens': 400,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return JsonResponse(
                {'error': f'IA retornou {resp.status_code}: {resp.text[:200]}'},
                status=502,
            )
        resumo = resp.json()['choices'][0]['message']['content'].strip()
    except Exception as exc:
        return JsonResponse({'error': f'Erro chamando IA: {exc}'}, status=500)

    cache.set(cache_key, resumo, timeout=3600)  # 1h

    # Auditoria
    from apps.sistema.utils import registrar_acao
    registrar_acao(
        'inbox', 'resumir_conversa', 'conversa', conversa.id,
        f'Resumo IA gerado ({len(mensagens)} msgs)',
        request=request,
    )

    return JsonResponse({
        'resumo': resumo,
        'from_cache': False,
        'mensagens_processadas': len(mensagens),
    })


@login_required
@require_http_methods(["POST"])
def api_avaliacao_responder(request, avaliacao_id):
    """
    Registra a nota CSAT (e opcional comentário) numa avaliação pendente.
    Usado quando o gerente CS recebe a resposta off-band e quer registrar manual.
    Body: {nota: 1-5, comentario?: str}
    """
    from apps.inbox.models import AvaliacaoAtendimento

    try:
        avaliacao = AvaliacaoAtendimento.objects.get(pk=avaliacao_id)
    except AvaliacaoAtendimento.DoesNotExist:
        return JsonResponse({'error': 'Avaliação não encontrada'}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    nota = data.get('nota')
    if nota is None or not isinstance(nota, int) or not (1 <= nota <= 5):
        return JsonResponse({'error': 'Nota deve ser inteiro de 1 a 5'}, status=400)

    avaliacao.nota = nota
    avaliacao.comentario = (data.get('comentario') or '').strip()
    avaliacao.data_resposta = timezone.now()

    # Classificar sentimento via IA se houver comentário
    if avaliacao.comentario:
        avaliacao.sentimento = _classificar_sentimento_csat(avaliacao.comentario, avaliacao.tenant)

    avaliacao.save(update_fields=['nota', 'comentario', 'sentimento', 'data_resposta'])

    # Notificar gerente se detrator
    if avaliacao.eh_detrator:
        try:
            from django.contrib.auth.models import User
            from apps.notificacoes.services import criar_notificacao
            gerentes = User.objects.filter(
                perfil__tenant=avaliacao.tenant,
                permissoes__perfil__nome__in=['Gerente CS', 'Gerente Suporte', 'Admin'],
                is_active=True,
            ).distinct()
            for g in gerentes:
                criar_notificacao(
                    tenant=avaliacao.tenant,
                    codigo_tipo='csat_detrator',
                    titulo=f'Detrator no atendimento (nota {nota}/5)',
                    mensagem=f'Conversa #{avaliacao.conversa.numero}: {avaliacao.comentario[:120] or "sem comentário"}',
                    destinatario=g,
                    url_acao=f'/inbox/?conversa={avaliacao.conversa_id}',
                    dados_contexto={'avaliacao_id': avaliacao.id, 'nota': nota},
                )
        except Exception as exc:
            logger.warning('Falha ao notificar detrator: %s', exc)

    return JsonResponse({
        'success': True,
        'nota': nota,
        'sentimento': avaliacao.sentimento,
        'eh_detrator': avaliacao.eh_detrator,
    })


def _classificar_sentimento_csat(comentario, tenant):
    """Classifica sentimento de comentário CSAT via LLM. Retorna 'positivo'|'neutro'|'negativo'."""
    try:
        from apps.integracoes.models import IntegracaoAPI
        import requests as http_requests

        integracao = IntegracaoAPI.all_tenants.filter(
            tenant=tenant, tipo__in=['openai', 'anthropic', 'groq'], ativa=True,
        ).first()
        if not integracao:
            return ''

        api_key = (integracao.api_key or integracao.configuracoes_extras.get('api_key', '') or integracao.access_token or '')
        modelo = integracao.configuracoes_extras.get('modelo', 'gpt-4o-mini')
        url = ('https://api.openai.com/v1/chat/completions' if integracao.tipo == 'openai'
               else 'https://api.groq.com/openai/v1/chat/completions' if integracao.tipo == 'groq'
               else integracao.base_url)

        resp = http_requests.post(
            url,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': modelo,
                'messages': [
                    {'role': 'system', 'content': 'Classifique o sentimento do comentário sobre atendimento. Responda APENAS uma palavra: positivo, neutro, ou negativo.'},
                    {'role': 'user', 'content': comentario[:500]},
                ],
                'temperature': 0.1,
                'max_tokens': 10,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return ''
        text = resp.json()['choices'][0]['message']['content'].strip().lower()
        for s in ('positivo', 'negativo', 'neutro'):
            if s in text:
                return s
        return ''
    except Exception as exc:
        logger.warning('Falha ao classificar sentimento CSAT: %s', exc)
        return ''


@login_required
def csat_dashboard(request):
    """Dashboard CSAT: NPS médio, distribuição 1-5, lista detratores."""
    from datetime import timedelta
    from django.db.models import Count, Avg
    from apps.inbox.models import AvaliacaoAtendimento

    dias = int(request.GET.get('dias', 30))
    desde = timezone.now() - timedelta(days=dias)

    qs = AvaliacaoAtendimento.objects.filter(criado_em__gte=desde)
    respondidas = qs.exclude(nota__isnull=True)
    pendentes = qs.filter(nota__isnull=True).count()

    total_resp = respondidas.count()
    csat_medio = respondidas.aggregate(media=Avg('nota'))['media'] or 0

    # Distribuição
    dist = {i: 0 for i in range(1, 6)}
    for item in respondidas.values('nota').annotate(qtd=Count('id')):
        dist[item['nota']] = item['qtd']

    detratores = (
        respondidas.filter(nota__lte=2)
        .select_related('conversa', 'conversa__lead')
        .order_by('-criado_em')[:30]
    )

    promotores = respondidas.filter(nota=5).count()
    neutros = respondidas.filter(nota__in=[3, 4]).count()
    qtd_detratores = respondidas.filter(nota__lte=2).count()

    return render(request, 'inbox/csat_dashboard.html', {
        'dias': dias,
        'csat_medio': round(csat_medio, 2),
        'total_respondidas': total_resp,
        'total_pendentes': pendentes,
        'distribuicao': [(nota, dist[nota], round(dist[nota] / total_resp * 100, 1) if total_resp else 0) for nota in range(5, 0, -1)],
        'promotores': promotores,
        'neutros': neutros,
        'detratores_qtd': qtd_detratores,
        'detratores_lista': detratores,
        'taxa_resposta': round(total_resp / qs.count() * 100, 1) if qs.count() else 0,
    })


def renderizar_resposta(conteudo, conversa, atendente=None):
    """
    Substitui variáveis {{var}} em conteudo pelos dados reais.
    Defensivo: variáveis sem dados retornam string vazia (em vez do placeholder).
    """
    if not conteudo or '{{' not in conteudo:
        return conteudo

    nome = (
        (conversa.lead.nome_razaosocial if conversa.lead else None)
        or conversa.contato_nome
        or 'cliente'
    )
    primeiro_nome = nome.split()[0] if nome else ''
    telefone = (conversa.lead.telefone if conversa.lead else None) or conversa.contato_telefone or ''
    email = (conversa.lead.email if conversa.lead else None) or conversa.contato_email or ''
    empresa = (conversa.lead.empresa if conversa.lead else '') or ''

    atendente_obj = atendente or conversa.agente
    atendente_nome = ''
    primeiro_nome_atendente = ''
    if atendente_obj:
        atendente_nome = atendente_obj.get_full_name() or atendente_obj.username
        primeiro_nome_atendente = atendente_nome.split()[0] if atendente_nome else ''

    substituicoes = {
        '{{nome_cliente}}': nome,
        '{{primeiro_nome}}': primeiro_nome,
        '{{telefone}}': telefone,
        '{{email}}': email,
        '{{atendente}}': atendente_nome,
        '{{primeiro_nome_atendente}}': primeiro_nome_atendente,
        '{{empresa}}': empresa,
    }

    resultado = conteudo
    for tag, valor in substituicoes.items():
        resultado = resultado.replace(tag, str(valor or ''))
    return resultado


@login_required
def api_etiquetas(request):
    """GET: Listar etiquetas disponíveis."""
    if not getattr(request, 'tenant', None):
        return JsonResponse({'error': 'Tenant não identificado.'}, status=403)
    etiquetas = EtiquetaConversa.all_tenants.filter(tenant=request.tenant)
    data = [
        {'id': e.id, 'nome': e.nome, 'cor_hex': e.cor_hex}
        for e in etiquetas
    ]
    return JsonResponse({'etiquetas': data})


@login_required
@require_http_methods(["GET", "POST"])
def api_atualizar_status_agente(request):
    """
    GET:  Retorna status atual do agente (cria perfil se nao existir).
    POST: Atualiza status do agente (online/ausente/offline).
    """
    from .models import PerfilAgenteInbox

    perfil, _ = PerfilAgenteInbox.all_tenants.get_or_create(
        user=request.user,
        tenant=request.tenant,
        defaults={}
    )

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'JSON inválido'}, status=400)

        novo_status = body.get('status')
        if novo_status not in ('online', 'ausente', 'offline'):
            return JsonResponse({'error': 'Status inválido'}, status=400)

        perfil.status = novo_status
        perfil.save(update_fields=['status', 'ultimo_status_em'])

    return JsonResponse({
        'success': True,
        'status': perfil.status,
        'capacidade_maxima': perfil.capacidade_maxima,
        'conversas_abertas': perfil.conversas_abertas_count,
    })


# ── Configurações ──────────────────────────────────────────────────

@login_required
def configuracoes_inbox(request):
    """Página de configurações do Inbox (equipes, filas, respostas, etc)."""
    denied = _check_perm(request, 'inbox.configurar')
    if denied: return denied
    from django.contrib import messages as django_messages

    if request.method == 'POST':
        action = request.POST.get('action', '')
        _processar_action_config(request, action, django_messages)

    # Horários globais como JSON para o template
    horarios_dict = {}
    for h in HorarioAtendimento.objects.filter(fila__isnull=True):
        horarios_dict[h.dia_semana] = {
            'ativo': h.ativo,
            'hora_inicio': h.hora_inicio.strftime('%H:%M') if h.hora_inicio else '',
            'hora_fim': h.hora_fim.strftime('%H:%M') if h.hora_fim else '',
        }

    # Horários por fila como JSON
    horarios_fila_dict = {}
    for h in HorarioAtendimento.objects.filter(fila__isnull=False):
        fila_id = str(h.fila_id)
        if fila_id not in horarios_fila_dict:
            horarios_fila_dict[fila_id] = {}
        horarios_fila_dict[fila_id][h.dia_semana] = {
            'ativo': h.ativo,
            'hora_inicio': h.hora_inicio.strftime('%H:%M') if h.hora_inicio else '',
            'hora_fim': h.hora_fim.strftime('%H:%M') if h.hora_fim else '',
        }

    widget_config = WidgetConfig.get_config()
    canal_widget = CanalInbox.objects.filter(tipo='widget').first()

    context = {
        'equipes': EquipeInbox.objects.prefetch_related('membros__user').filter(ativo=True),
        'filas': FilaInbox.objects.select_related('equipe').prefetch_related('regras'),
        'respostas': RespostaRapida.objects.all(),
        'etiquetas_list': EtiquetaConversa.objects.all(),
        'canais': CanalInbox.objects.select_related('integracao').all(),
        'integracoes_disponiveis': IntegracaoAPI.objects.filter(tipo__in=['uazapi', 'evolution', 'meta_cloud', 'twilio_whatsapp']),
        'fluxos_atendimento': _get_fluxos_atendimento(),
        'horarios_json': json.dumps(horarios_dict),
        'horarios_fila_json': json.dumps(horarios_fila_dict),
        'config': ConfiguracaoInbox.get_config(),
        'categorias_faq': CategoriaFAQ.objects.prefetch_related('artigos').filter(ativo=True),
        'widget_config': widget_config,
        'canal_widget': canal_widget,
        'usuarios': User.objects.filter(is_active=True, perfil__tenant=request.tenant).order_by('first_name'),
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
            if EquipeInbox.objects.filter(nome=nome).exists():
                django_messages.warning(request, f'Equipe "{nome}" ja existe.')
            else:
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
            PerfilAgenteInbox.all_tenants.get_or_create(
                user=user,
                tenant=equipe.tenant,
                defaults={}
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

            # Vincular integracao e provedor
            integracao_id = request.POST.get('integracao_id', '')
            if integracao_id:
                integ = IntegracaoAPI.objects.filter(pk=integracao_id).first()
                if integ:
                    canal.integracao = integ
                    canal.provedor = integ.tipo
            else:
                canal.integracao = None
                canal.provedor = ''

            # Vincular fluxo de atendimento
            fluxo_id = request.POST.get('fluxo_id', '')
            if fluxo_id:
                from apps.comercial.atendimento.models import FluxoAtendimento
                fluxo = FluxoAtendimento.objects.filter(pk=fluxo_id, ativo=True).first()
                canal.fluxo = fluxo
            else:
                canal.fluxo = None

            canal.save(update_fields=['configuracao', 'integracao', 'provedor', 'fluxo'])
            django_messages.success(request, f'Canal "{canal.nome}" atualizado.')

    elif action == 'criar_canal':
        nome = request.POST.get('nome', '').strip()
        tipo = request.POST.get('tipo', 'whatsapp')
        integracao_id = request.POST.get('integracao_id', '')
        if nome:
            # Verificar se ja existe canal do mesmo tipo para este tenant
            existente = CanalInbox.objects.filter(tenant=request.tenant, tipo=tipo, identificador_canal='').first()
            if existente:
                django_messages.warning(request, f'Ja existe um canal do tipo "{tipo}". Edite o existente.')
            else:
                canal = CanalInbox(tenant=request.tenant, nome=nome, tipo=tipo)
                if integracao_id:
                    integ = IntegracaoAPI.objects.filter(pk=integracao_id).first()
                    if integ:
                        canal.integracao = integ
                        canal.provedor = integ.tipo
                canal.save()
                django_messages.success(request, f'Canal "{nome}" criado.')

    # ── Horário de Atendimento (global) ──────────────────────────
    elif action == 'salvar_horario':
        for dia in range(7):
            ativo = request.POST.get(f'dia_{dia}_ativo') == 'on'
            inicio = request.POST.get(f'dia_{dia}_inicio', '')
            fim = request.POST.get(f'dia_{dia}_fim', '')
            if inicio and fim:
                obj, _ = HorarioAtendimento.objects.get_or_create(
                    dia_semana=dia, fila__isnull=True,
                    defaults={'hora_inicio': inicio, 'hora_fim': fim, 'ativo': ativo}
                )
                obj.hora_inicio = inicio
                obj.hora_fim = fim
                obj.ativo = ativo
                obj.fila = None
                obj.save()
        django_messages.success(request, 'Horarios globais salvos.')

    # ── Horário por Fila ──────────────────────────────────────────
    elif action == 'salvar_horario_fila':
        fila_id = request.POST.get('fila_id')
        fila = FilaInbox.objects.filter(pk=fila_id).first()
        if fila:
            for dia in range(7):
                ativo = request.POST.get(f'fila_dia_{dia}_ativo') == 'on'
                inicio = request.POST.get(f'fila_dia_{dia}_inicio', '')
                fim = request.POST.get(f'fila_dia_{dia}_fim', '')
                if inicio and fim:
                    obj, _ = HorarioAtendimento.objects.get_or_create(
                        fila=fila, dia_semana=dia,
                        defaults={'hora_inicio': inicio, 'hora_fim': fim, 'ativo': ativo}
                    )
                    obj.hora_inicio = inicio
                    obj.hora_fim = fim
                    obj.ativo = ativo
                    obj.save()
                else:
                    HorarioAtendimento.objects.filter(fila=fila, dia_semana=dia).delete()
            # Mensagem fora do horario da fila
            msg = request.POST.get('mensagem_fora_horario_fila', '')
            fila.mensagem_fora_horario = msg
            fila.save(update_fields=['mensagem_fora_horario'])
            django_messages.success(request, f'Horarios da fila "{fila.nome}" salvos.')

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

        # Vincular fluxo ao canal widget
        widget_fluxo_id = request.POST.get('widget_fluxo_id', '')
        canal_widget = CanalInbox.objects.filter(tipo='widget').first()
        if canal_widget:
            if widget_fluxo_id:
                from apps.comercial.atendimento.models import FluxoAtendimento
                fluxo = FluxoAtendimento.objects.filter(pk=widget_fluxo_id, ativo=True).first()
                canal_widget.fluxo = fluxo
            else:
                canal_widget.fluxo = None
            canal_widget.save(update_fields=['fluxo'])

        django_messages.success(request, 'Widget atualizado.')


# ── Dashboard de Métricas ──────────────────────────────────────────

@login_required
def dashboard_inbox(request):
    """Dashboard com visao em tempo real do inbox."""
    from datetime import timedelta
    from django.db.models import Count, Avg, Q
    from django.db.models.functions import TruncDate

    hoje = timezone.now().date()
    conversas = Conversa.objects.all()
    ativas = conversas.filter(status__in=['aberta', 'pendente'])

    # === TEMPO REAL ===
    no_bot = ativas.filter(modo_atendimento='bot').count()
    na_fila = ativas.filter(modo_atendimento='humano', agente__isnull=True).count()
    em_atendimento = ativas.filter(modo_atendimento='humano', agente__isnull=False).count()
    pendentes = ativas.filter(status='pendente').count()
    resolvidas_hoje = conversas.filter(status='resolvida', data_resolucao__date=hoje).count()
    total_hoje = conversas.filter(data_abertura__date=hoje).count()

    # Tempo medio de espera na fila (conversas sem agente)
    from django.utils import timezone as tz
    agora = tz.now()
    sem_agente = ativas.filter(modo_atendimento='humano', agente__isnull=True)
    if sem_agente.exists():
        tempos_espera = [(agora - c.data_abertura).total_seconds() / 60 for c in sem_agente]
        tempo_medio_fila = sum(tempos_espera) / len(tempos_espera)
    else:
        tempo_medio_fila = 0

    # === AGENTES ===
    agentes_data = []
    # Filtrar agentes que pertencem a equipes do tenant
    equipes_tenant = EquipeInbox.objects.filter(ativo=True).values_list('id', flat=True)
    membros_ids = MembroEquipeInbox.objects.filter(equipe_id__in=equipes_tenant).values_list('user_id', flat=True)
    for perfil in PerfilAgenteInbox.objects.select_related('user').filter(user_id__in=membros_ids):
        conversas_ativas = ativas.filter(agente=perfil.user).count()
        agentes_data.append({
            'nome': perfil.user.get_full_name() or perfil.user.username,
            'status': perfil.status,
            'conversas_ativas': conversas_ativas,
            'capacidade': perfil.capacidade_maxima,
        })
    agentes_data.sort(key=lambda a: (0 if a['status'] == 'online' else 1 if a['status'] == 'ausente' else 2, a['nome']))

    # === FILAS ===
    filas_data = []
    for fila in FilaInbox.objects.select_related('equipe').filter(ativo=True):
        aguardando = ativas.filter(fila=fila, agente__isnull=True).count()
        em_atend_fila = ativas.filter(fila=fila, agente__isnull=False).count()
        agentes_online = PerfilAgenteInbox.objects.filter(
            user__in=fila.equipe.membros.values_list('user', flat=True),
            status='online',
        ).count()
        from .distribution import verificar_horario_fila
        dentro_horario = verificar_horario_fila(fila)
        filas_data.append({
            'nome': fila.nome,
            'equipe': fila.equipe.nome,
            'aguardando': aguardando,
            'em_atendimento': em_atend_fila,
            'agentes_online': agentes_online,
            'dentro_horario': dentro_horario,
            'modo': fila.get_modo_distribuicao_display(),
        })

    # === HISTORICO ===
    trinta_dias = hoje - timedelta(days=30)
    por_canal = conversas.exclude(status='arquivada').values(
        'canal__nome'
    ).annotate(total=Count('id')).order_by('-total')

    por_agente = conversas.filter(
        agente__isnull=False, status='resolvida',
        data_resolucao__date__gte=trinta_dias,
    ).values(
        'agente__first_name', 'agente__last_name'
    ).annotate(
        total_resolvidas=Count('id'),
        avg_tempo=Avg('tempo_primeira_resposta_seg'),
    ).order_by('-total_resolvidas')[:10]

    # Volume 30 dias
    volume_por_dia = dict(
        conversas.filter(
            data_abertura__date__gte=trinta_dias
        ).annotate(dia=TruncDate('data_abertura')).values('dia').annotate(
            total=Count('id')
        ).values_list('dia', 'total')
    )
    ultimos_30 = []
    for i in range(29, -1, -1):
        dia = hoje - timedelta(days=i)
        ultimos_30.append({'dia': dia.strftime('%d/%m'), 'count': volume_por_dia.get(dia, 0)})

    context = {
        # Tempo real
        'no_bot': no_bot,
        'na_fila': na_fila,
        'em_atendimento': em_atendimento,
        'pendentes': pendentes,
        'resolvidas_hoje': resolvidas_hoje,
        'total_hoje': total_hoje,
        'tempo_medio_fila': tempo_medio_fila,
        # Agentes
        'agentes_data': agentes_data,
        # Filas
        'filas_data': filas_data,
        # Historico
        'por_canal': por_canal,
        'por_agente': por_agente,
        'ultimos_30_json': json.dumps(ultimos_30),
        'page_title': 'Central de Atendimento',
    }
    return render(request, 'inbox/dashboard_inbox.html', context)
