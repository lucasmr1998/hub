"""
Endpoints do editor de automação.

- `nodes_catalogo_api`: lista os tipos de nó registrados (paleta do editor).
- `testar_fluxo_api`: roda um fluxo (grafo JSON) via `executar_fluxo` e devolve o
  trace. Sem persistência — o editor manda o grafo, o backend executa e responde.
"""
import json

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Fluxo, ExecucaoFluxo
from .nodes import Contexto, REGISTRY
from .runtime import executar_fluxo, validar_fluxo


def _corpo_json(request):
    try:
        return json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return None


def _ensure_webhook_token(fluxo):
    """Gera o token se o grafo tem um nó-gatilho webhook e ainda não há token."""
    import secrets
    nodes = (fluxo.grafo or {}).get('nodes') or {}
    tem_webhook = any((n or {}).get('tipo') == 'webhook' for n in nodes.values())
    if tem_webhook and not fluxo.webhook_token:
        fluxo.webhook_token = secrets.token_urlsafe(24)
        fluxo.save(update_fields=['webhook_token', 'atualizado_em'])
    return fluxo.webhook_token


@ensure_csrf_cookie  # garante o cookie csrftoken pro editor mandar no X-CSRFToken
@login_required
def editor_page(request):
    """Serve o editor (bundle React buildado) como página única do app.

    Passa `v` (mtime do bundle) pro template fazer cache-bust — o nome do arquivo
    é fixo (editor.js), então sem isso o navegador serve a versão velha do cache.
    """
    import os
    bundle = os.path.join(os.path.dirname(__file__), 'static', 'automacao_editor', 'editor.js')
    try:
        v = str(int(os.path.getmtime(bundle)))
    except OSError:
        v = ''
    return render(request, 'automacao/editor.html', {'v': v})


@login_required
def execucoes_page(request):
    """Observabilidade: lista as execuções de fluxo do tenant (status, trace, erro)."""
    from django.core.paginator import Paginator
    from django.db.models import Count

    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return render(request, 'automacao/execucoes.html', {'sem_tenant': True})

    qs = (ExecucaoFluxo.all_tenants
          .filter(tenant=tenant)
          .select_related('fluxo')
          .order_by('-criado_em'))

    status = (request.GET.get('status') or '').strip()
    if status:
        qs = qs.filter(status=status)
    fluxo_id = (request.GET.get('fluxo') or '').strip()
    if fluxo_id.isdigit():
        qs = qs.filter(fluxo_id=int(fluxo_id))

    # Contadores por status (sobre o tenant inteiro, sem o filtro de status).
    base = ExecucaoFluxo.all_tenants.filter(tenant=tenant)
    contagem = {r['status']: r['n'] for r in base.values('status').annotate(n=Count('id'))}
    stats = {
        'total': sum(contagem.values()),
        'completado': contagem.get('completado', 0),
        'erro': contagem.get('erro', 0),
        'aguardando': contagem.get('aguardando', 0) + contagem.get('pendente', 0),
    }

    pagina = Paginator(qs, 30).get_page(request.GET.get('p'))
    return render(request, 'automacao/execucoes.html', {
        'execucoes': pagina,
        'stats': stats,
        'status_atual': status,
        'status_opcoes': ['pendente', 'rodando', 'aguardando', 'completado', 'erro'],
    })


@login_required
def opcoes_api(request, fonte):
    """Opções dinâmicas de uma fonte (segmentos, pipelines, estágios, responsáveis…)
    pro tenant — alimenta os dropdowns dinâmicos do editor."""
    from .opcoes import opcoes_de
    return JsonResponse({'opcoes': opcoes_de(fonte, getattr(request, 'tenant', None))})


@login_required
def execucoes_api(request):
    """JSON das execuções do tenant — alimenta a aba 'Execuções' DENTRO do editor
    (sem sair da página). Opcional `?fluxo=<id>` e `?status=<s>`."""
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'sem tenant'}, status=400)
    qs = (ExecucaoFluxo.all_tenants.filter(tenant=tenant)
          .select_related('fluxo').order_by('-criado_em'))
    fluxo_id = (request.GET.get('fluxo') or '').strip()
    if fluxo_id.isdigit():
        qs = qs.filter(fluxo_id=int(fluxo_id))
    status = (request.GET.get('status') or '').strip()
    if status:
        qs = qs.filter(status=status)
    execs = [{
        'id': e.pk,
        'fluxo': e.fluxo.nome or '(sem nome)',
        'fluxo_id': e.fluxo_id,
        'status': e.status,
        'quando': e.criado_em.strftime('%d/%m/%Y %H:%M'),
        'erro': e.erro or '',
        'trace': e.trace or [],
    } for e in qs[:100]]
    return JsonResponse({'execucoes': execs})


@login_required
def nodes_catalogo_api(request):
    """Paleta: tipos de nó disponíveis pro editor montar a barra de blocos."""
    return JsonResponse({'nodes': [
        {
            'tipo': n.tipo, 'label': n.label, 'icone': n.icone,
            'grupo': n.grupo, 'subgrupo': n.subgrupo, 'categoria': n.categoria,
            'saidas': n.saidas, 'is_trigger': n.is_trigger, 'campos': n.campos_config(),
        }
        for n in REGISTRY.values()
    ]})


@require_POST
@login_required
def testar_fluxo_api(request):
    """Roda um fluxo postado pelo editor e devolve o trace. Não persiste nada."""
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'JSON inválido'}, status=400)

    fluxo = payload.get('fluxo') or {}
    ctx_raw = payload.get('contexto') or {}

    erros = validar_fluxo(fluxo)
    if erros:
        return JsonResponse({'erro': 'Fluxo inválido', 'detalhes': erros}, status=400)

    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'Sem tenant na sessão.'}, status=400)

    contexto = Contexto(
        tenant=tenant,
        variaveis=ctx_raw.get('variaveis'),
        nodes=ctx_raw.get('nodes'),
    )
    resultado = executar_fluxo(fluxo, contexto)
    return JsonResponse({
        'status': resultado.status,
        'erro': resultado.erro,
        'passos': [
            {'handle': p.handle, 'tipo': p.tipo, 'status': p.status,
             'branch': p.branch, 'erro': p.erro}
            for p in resultado.passos
        ],
        'variaveis': contexto.variaveis,
        'nodes': contexto.nodes,
    })


@login_required
def fluxos_api(request):
    """Lista (GET) e cria (POST) fluxos do tenant da sessão."""
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'Sem tenant na sessão.'}, status=400)

    if request.method == 'GET':
        fluxos = list(
            Fluxo.all_tenants.filter(tenant=tenant).values('id', 'nome', 'ativo', 'atualizado_em')
        )
        return JsonResponse({'fluxos': fluxos})

    if request.method == 'POST':
        data = _corpo_json(request)
        if data is None:
            return JsonResponse({'erro': 'JSON inválido'}, status=400)
        nome = (data.get('nome') or '').strip()
        if not nome:
            return JsonResponse({'erro': 'nome obrigatório'}, status=400)
        fluxo = Fluxo.objects.create(
            tenant=tenant,
            nome=nome,
            grafo=data.get('grafo') or {},
            criado_por=request.user if request.user.is_authenticated else None,
        )
        token = _ensure_webhook_token(fluxo)
        return JsonResponse({'id': fluxo.id, 'nome': fluxo.nome, 'webhook_token': token})

    return JsonResponse({'erro': 'método não suportado'}, status=405)


@login_required
def fluxo_api(request, pk):
    """Lê (GET), atualiza (PUT/POST) e remove (DELETE) um fluxo do tenant."""
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'Sem tenant na sessão.'}, status=400)

    fluxo = Fluxo.all_tenants.filter(tenant=tenant, pk=pk).first()
    if fluxo is None:
        return JsonResponse({'erro': 'fluxo não encontrado'}, status=404)

    if request.method == 'GET':
        return JsonResponse({
            'id': fluxo.id, 'nome': fluxo.nome, 'grafo': fluxo.grafo,
            'webhook_token': fluxo.webhook_token,
        })

    if request.method in ('PUT', 'POST'):
        data = _corpo_json(request)
        if data is None:
            return JsonResponse({'erro': 'JSON inválido'}, status=400)
        if data.get('nome'):
            fluxo.nome = data['nome'].strip()
        if 'grafo' in data:
            fluxo.grafo = data['grafo'] or {}
        fluxo.save()
        token = _ensure_webhook_token(fluxo)
        return JsonResponse({'id': fluxo.id, 'nome': fluxo.nome, 'webhook_token': token})

    if request.method == 'DELETE':
        fluxo.delete()
        return JsonResponse({'ok': True})

    return JsonResponse({'erro': 'método não suportado'}, status=405)


@require_POST
@login_required
def fluxo_webhook_api(request, pk):
    """Ativa o gatilho webhook do fluxo (gera token) e devolve a URL."""
    import secrets
    tenant = getattr(request, 'tenant', None)
    fluxo = Fluxo.all_tenants.filter(tenant=tenant, pk=pk).first()
    if fluxo is None:
        return JsonResponse({'erro': 'fluxo não encontrado'}, status=404)
    if not fluxo.webhook_token:
        fluxo.webhook_token = secrets.token_urlsafe(24)
        fluxo.save(update_fields=['webhook_token', 'atualizado_em'])
    url = request.build_absolute_uri(f'/automacao/webhook/{fluxo.webhook_token}/')
    return JsonResponse({'webhook_token': fluxo.webhook_token, 'url': url})


_WEBHOOK_LIMITE = 60       # requisições por janela, por token
_WEBHOOK_JANELA = 60       # segundos
_WEBHOOK_MAX_BYTES = 256 * 1024  # 256 KB de payload


def _webhook_rate_limited(token):
    chave = f'automacao_wh:{token}'
    try:
        atual = cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, _WEBHOOK_JANELA)
        atual = 1
    return atual > _WEBHOOK_LIMITE


@login_required
def eventos_api(request):
    """Catálogo de eventos do sistema (+ subcampos) pro nó Evento e seus filtros."""
    from .eventos import catalogo
    return JsonResponse({'eventos': catalogo()})


@csrf_exempt  # webhook público (inbound, server-to-server) — autenticado pelo token na URL
@require_POST
def webhook_receber(request, token):
    """Dispara um fluxo via webhook. O corpo JSON vira `{{var.payload}}`."""
    fluxo = Fluxo.all_tenants.filter(webhook_token=token, ativo=True).first() if token else None
    if fluxo is None:
        return JsonResponse({'erro': 'webhook não encontrado'}, status=404)
    if len(request.body or b'') > _WEBHOOK_MAX_BYTES:
        return JsonResponse({'erro': 'payload muito grande'}, status=413)
    if _webhook_rate_limited(token):
        return JsonResponse({'erro': 'rate limit'}, status=429)
    payload = _corpo_json(request)
    if payload is None:
        payload = {}
    from .execucao import executar_e_persistir
    contexto = Contexto(tenant=fluxo.tenant, variaveis={'payload': payload})
    execucao, res = executar_e_persistir(fluxo, contexto)
    return JsonResponse({'execucao_id': execucao.id, 'status': res.status})
