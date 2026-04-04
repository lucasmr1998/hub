"""
Views públicas do widget (sem login).
Autenticação via token público do WidgetConfig.
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CategoriaFAQ, ArtigoFAQ, Conversa, Mensagem
from .widget_auth import widget_token_required
from . import services


@widget_token_required
def widget_config(request):
    """GET: Retorna config do widget + categorias FAQ."""
    wc = request.widget_config

    categorias = []
    if wc.mostrar_faq:
        cats = CategoriaFAQ.all_tenants.filter(
            tenant=request.tenant, ativo=True
        ).prefetch_related('artigos')
        categorias = [
            {
                'id': c.id,
                'nome': c.nome,
                'slug': c.slug,
                'icone': c.icone,
                'cor': c.cor,
                'artigos_count': c.artigos.filter(ativo=True).count(),
            }
            for c in cats
        ]

    return JsonResponse({
        'titulo': wc.titulo,
        'mensagem_boas_vindas': wc.mensagem_boas_vindas,
        'cor_primaria': wc.cor_primaria,
        'cor_header': wc.cor_header,
        'posicao': wc.posicao,
        'mostrar_faq': wc.mostrar_faq,
        'pedir_dados_antes': wc.pedir_dados_antes,
        'campos_obrigatorios': wc.campos_obrigatorios,
        'categorias': categorias,
    })


@widget_token_required
def widget_faq(request):
    """GET: Artigos de uma categoria FAQ."""
    slug = request.GET.get('categoria', '')
    if not slug:
        return JsonResponse({'artigos': []})

    artigos = ArtigoFAQ.all_tenants.filter(
        tenant=request.tenant,
        categoria__slug=slug,
        categoria__ativo=True,
        ativo=True,
    ).values('id', 'titulo', 'conteudo', 'visualizacoes')

    return JsonResponse({'artigos': list(artigos)})


@widget_token_required
def widget_faq_buscar(request):
    """GET: Busca artigos por título/conteúdo."""
    from django.db.models import Q

    q = request.GET.get('q', '').strip()[:100]
    if not q:
        return JsonResponse({'artigos': []})

    artigos = ArtigoFAQ.all_tenants.filter(
        tenant=request.tenant, ativo=True,
    ).filter(
        Q(titulo__icontains=q) | Q(conteudo__icontains=q)
    ).values('id', 'titulo', 'conteudo', 'categoria__nome')[:20]

    return JsonResponse({'artigos': list(artigos)})


@csrf_exempt
@widget_token_required
@require_http_methods(["POST"])
def widget_conversa_iniciar(request):
    """POST: Inicia ou retoma conversa do visitante."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    visitor_id = body.get('visitor_id', '').strip()
    nome = body.get('nome', '').strip()[:255]
    email = body.get('email', '').strip()[:200]
    telefone = body.get('telefone', '').strip()[:20]
    mensagem = body.get('mensagem', '').strip()[:5000]

    if not visitor_id:
        return JsonResponse({'error': 'visitor_id obrigatório'}, status=400)
    if not mensagem:
        return JsonResponse({'error': 'mensagem obrigatória'}, status=400)

    conversa, msg, nova = services.receber_mensagem_widget(
        visitor_id=visitor_id,
        nome=nome or 'Visitante',
        conteudo=mensagem,
        tenant=request.tenant,
        email=email,
        telefone=telefone,
    )

    # Buscar todas as mensagens para retornar
    mensagens = _serializar_mensagens(conversa, visitor_id)

    return JsonResponse({
        'conversa_id': conversa.id,
        'nova_conversa': nova,
        'mensagens': mensagens,
    })


@widget_token_required
def widget_mensagens(request, conversa_id):
    """GET: Mensagens de uma conversa (validando visitor_id)."""
    visitor_id = request.GET.get('visitor_id', '')
    conversa = _get_widget_conversa(conversa_id, visitor_id, request.tenant)
    if not conversa:
        return JsonResponse({'error': 'Conversa não encontrada'}, status=404)

    mensagens = _serializar_mensagens(conversa, visitor_id)
    return JsonResponse({'mensagens': mensagens})


@csrf_exempt
@widget_token_required
@require_http_methods(["POST"])
def widget_enviar(request, conversa_id):
    """POST: Visitante envia mensagem."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    visitor_id = body.get('visitor_id', '')
    conteudo = body.get('conteudo', '').strip()[:5000]

    if not conteudo:
        return JsonResponse({'error': 'conteudo obrigatório'}, status=400)

    conversa = _get_widget_conversa(conversa_id, visitor_id, request.tenant)
    if not conversa:
        return JsonResponse({'error': 'Conversa não encontrada'}, status=404)

    msg = Mensagem(
        tenant=request.tenant,
        conversa=conversa,
        remetente_tipo='contato',
        remetente_nome=conversa.contato_nome,
        tipo_conteudo='texto',
        conteudo=conteudo,
    )
    msg.save()

    conversa.ultima_mensagem_em = msg.data_envio
    conversa.ultima_mensagem_preview = conteudo[:255]
    conversa.mensagens_nao_lidas = (conversa.mensagens_nao_lidas or 0) + 1

    if conversa.status in ['resolvida', 'arquivada']:
        conversa.status = 'aberta'
        conversa.data_resolucao = None

    conversa.save(update_fields=[
        'ultima_mensagem_em', 'ultima_mensagem_preview',
        'mensagens_nao_lidas', 'status', 'data_resolucao',
    ])

    services._notificar_ws_nova_mensagem(conversa, msg)

    return JsonResponse({'success': True, 'mensagem_id': msg.id})


@widget_token_required
def widget_conversas(request):
    """GET: Lista conversas do visitante."""
    visitor_id = request.GET.get('visitor_id', '')
    if not visitor_id:
        return JsonResponse({'conversas': []})

    conversas = Conversa.all_tenants.filter(
        tenant=request.tenant,
        canal__tipo='widget',
        identificador_externo=visitor_id,
    ).order_by('-ultima_mensagem_em')[:20]

    data = [
        {
            'id': c.id,
            'status': c.status,
            'ultima_mensagem_preview': c.ultima_mensagem_preview,
            'ultima_mensagem_em': c.ultima_mensagem_em.isoformat() if c.ultima_mensagem_em else '',
            'mensagens_nao_lidas': c.mensagens_nao_lidas,
        }
        for c in conversas
    ]

    return JsonResponse({'conversas': data})


# ── Helpers ────────────────────────────────────────────────────────────

def _get_widget_conversa(conversa_id, visitor_id, tenant):
    """Busca conversa validando que pertence ao visitor_id."""
    if not visitor_id:
        return None
    return Conversa.all_tenants.filter(
        pk=conversa_id,
        tenant=tenant,
        canal__tipo='widget',
        identificador_externo=visitor_id,
    ).first()


def _serializar_mensagens(conversa, visitor_id):
    """Serializa mensagens seguras para o visitante (sem dados internos)."""
    msgs = conversa.mensagens.select_related('remetente_user').order_by('data_envio')

    resultado = []
    for m in msgs:
        # Filtrar mensagens de sistema internas
        if m.remetente_tipo == 'sistema' and m.tipo_conteudo == 'sistema':
            continue

        nome = m.remetente_nome
        if m.remetente_tipo == 'agente' and m.remetente_user:
            nome = m.remetente_user.first_name or 'Atendente'

        resultado.append({
            'id': m.id,
            'remetente_tipo': m.remetente_tipo,
            'remetente_nome': nome,
            'conteudo': m.conteudo,
            'tipo_conteudo': m.tipo_conteudo,
            'data_envio': m.data_envio.isoformat(),
        })

    return resultado
