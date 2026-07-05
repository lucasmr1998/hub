"""
Endpoints do editor de automação.

- `nodes_catalogo_api`: lista os tipos de nó registrados (paleta do editor).
- `testar_fluxo_api`: roda um fluxo (grafo JSON) via `executar_fluxo` e devolve o
  trace. Sem persistência — o editor manda o grafo, o backend executa e responde.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.utils import registrar_acao

from .models import Fluxo, ExecucaoFluxo
from .nodes import Contexto, REGISTRY
from .runtime import executar_fluxo, validar_fluxo, FluxoInvalido

logger = logging.getLogger(__name__)


def _exige_ver(request):
    """Bloqueia (403 JSON) se o usuário não tem `automacao.ver`. Devolve None se pode seguir."""
    if not user_tem_funcionalidade(request, 'automacao.ver'):
        return JsonResponse({'erro': 'Sem permissão'}, status=403)
    return None


def _exige_gerenciar(request):
    """Bloqueia (403 JSON) se o usuário não tem `automacao.gerenciar`. Devolve None se pode seguir."""
    if not user_tem_funcionalidade(request, 'automacao.gerenciar'):
        return JsonResponse({'erro': 'Sem permissão'}, status=403)
    return None


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
    if not user_tem_funcionalidade(request, 'automacao.ver'):
        return HttpResponseForbidden('Sem permissão')
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
    if not user_tem_funcionalidade(request, 'automacao.ver'):
        return HttpResponseForbidden('Sem permissão')
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
    neg = _exige_ver(request)
    if neg:
        return neg
    from .opcoes import opcoes_de
    return JsonResponse({'opcoes': opcoes_de(fonte, getattr(request, 'tenant', None))})


@login_required
def execucoes_api(request):
    """JSON das execuções do tenant — alimenta a aba 'Execuções' DENTRO do editor
    (sem sair da página). Opcional `?fluxo=<id>` e `?status=<s>`."""
    neg = _exige_ver(request)
    if neg:
        return neg
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
def execucao_detalhe_api(request, pk):
    """Uma execução com o grafo + estado (variaveis/nodes) + trace — pro editor
    REPRODUZIR a execução no canvas (caminho verde + I/O por nó), estilo n8n."""
    neg = _exige_ver(request)
    if neg:
        return neg
    tenant = getattr(request, 'tenant', None)
    e = (ExecucaoFluxo.all_tenants.filter(tenant=tenant, pk=pk)
         .select_related('fluxo').first())
    if e is None:
        return JsonResponse({'erro': 'execução não encontrada'}, status=404)
    estado = e.estado or {}
    return JsonResponse({
        'id': e.pk,
        'fluxo_id': e.fluxo_id,
        'grafo': (e.fluxo.grafo or {}),
        'variaveis': estado.get('variaveis') or {},
        'nodes': estado.get('nodes') or {},
        'trace': e.trace or [],
        'status': e.status,
        'erro': e.erro or '',
    })


@login_required
def agentes_page(request):
    """Consolidado: a gerencia de agentes mora no Workspace (casa unica).
    Mantido como redirect pra nao quebrar links/bookmarks antigos."""
    if not user_tem_funcionalidade(request, 'automacao.ver'):
        return HttpResponseForbidden('Sem permissão')
    from django.shortcuts import redirect
    return redirect('workspace:agentes_lista')


@login_required
def agente_editar_page(request, pk=None):
    """Consolidado: o editor de agentes mora no Workspace. Redirect (mantem o pk)."""
    if not user_tem_funcionalidade(request, 'automacao.ver'):
        return HttpResponseForbidden('Sem permissão')
    from django.shortcuts import redirect
    if pk:
        return redirect('workspace:agente_editar', pk=pk)
    return redirect('workspace:agente_novo')


@require_POST
@login_required
def agente_salvar(request):
    """Cria/atualiza um Agente do tenant (form POST)."""
    neg = _exige_gerenciar(request)
    if neg:
        return neg
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'sem tenant'}, status=400)
    from .models import Agente
    from apps.integracoes.models import IntegracaoAPI

    nome = (request.POST.get('nome') or '').strip()
    if not nome:
        return JsonResponse({'erro': 'nome obrigatório'}, status=400)

    integracao = None
    integ_id = (request.POST.get('integracao_ia') or '').strip()
    if integ_id.isdigit():
        integracao = IntegracaoAPI.all_tenants.filter(tenant=tenant, id=int(integ_id)).first()

    pk = (request.POST.get('id') or '').strip()
    criando = not pk.isdigit()
    if not criando:
        agente = Agente.all_tenants.filter(tenant=tenant, pk=int(pk)).first()
        if agente is None:
            return JsonResponse({'erro': 'agente não encontrado'}, status=404)
    else:
        agente = Agente(tenant=tenant,
                        criado_por=request.user if request.user.is_authenticated else None)

    agente.nome = nome
    agente.integracao_ia = integracao
    agente.modelo = (request.POST.get('modelo') or '').strip()
    agente.system_prompt = request.POST.get('system_prompt') or ''
    agente.ativo = (request.POST.get('ativo') or '') in ('on', 'true', '1')
    agente.tools = [t for t in request.POST.getlist('tools') if t]
    agente.base_categorias = [c for c in request.POST.getlist('base_categorias') if c]
    agente.save()
    try:
        acao = 'criar' if criando else 'editar'
        registrar_acao('config', acao, 'agente', agente.pk,
                        f"Agente '{agente.nome}' {'criado' if criando else 'atualizado'}",
                        request=request)
    except Exception:
        pass
    return JsonResponse({'ok': True, 'id': agente.pk})


@require_POST
@login_required
def agente_excluir(request, pk):
    """Remove um Agente do tenant."""
    neg = _exige_gerenciar(request)
    if neg:
        return neg
    tenant = getattr(request, 'tenant', None)
    from .models import Agente
    agente = Agente.all_tenants.filter(tenant=tenant, pk=pk).first()
    if agente is None:
        return JsonResponse({'erro': 'agente não encontrado'}, status=404)
    nome = agente.nome
    agente.delete()
    try:
        registrar_acao('config', 'excluir', 'agente', pk,
                        f"Agente '{nome}' excluído", request=request)
    except Exception:
        pass
    return JsonResponse({'ok': True})


@require_POST
@login_required
def agente_simular_api(request):
    """Simulador de conversa: roda o agente com o histórico do chat + tools (que rodam
    de verdade em dev), e devolve a resposta + quais tools dispararam. Sem WhatsApp."""
    neg = _exige_gerenciar(request)
    if neg:
        return neg
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'sem tenant'}, status=400)
    from .models import Agente
    from .nodes import Contexto
    from .services.ia import chamar_llm, chamar_llm_com_tools, integracao_ia_do_tenant
    from .services.ia_tools import schema_openai, despachar

    data = _corpo_json(request) or {}
    mensagem = (data.get('mensagem') or '').strip()
    if not mensagem:
        return JsonResponse({'erro': 'mensagem vazia'}, status=400)
    agente = (Agente.all_tenants.filter(tenant=tenant, pk=data.get('agente_id'))
              .select_related('integracao_ia').first())
    if agente is None:
        return JsonResponse({'erro': 'agente não encontrado'}, status=404)
    integracao = agente.integracao_ia or integracao_ia_do_tenant(tenant)
    if integracao is None:
        return JsonResponse({'erro': 'sem integração de IA ativa'}, status=400)

    messages = []
    if agente.system_prompt:
        messages.append({'role': 'system', 'content': agente.system_prompt})
    for m in (data.get('historico') or []):
        if m.get('role') in ('user', 'assistant') and m.get('content'):
            messages.append({'role': m['role'], 'content': m['content']})
    messages.append({'role': 'user', 'content': mensagem})

    contexto = Contexto(tenant=tenant, variaveis={'conteudo': mensagem})
    chamadas = []
    schema = schema_openai(list(agente.tools or []))
    if schema:
        def _disp(nome, args):
            chamadas.append(nome)
            return despachar(nome, args, contexto, agente)
        resposta = chamar_llm_com_tools(integracao, messages, schema, _disp, modelo=agente.modelo or None)
    else:
        resposta = chamar_llm(integracao, messages, modelo=agente.modelo or None)
    if resposta is None:
        return JsonResponse({'erro': 'falha ao chamar o LLM'}, status=502)
    return JsonResponse({'resposta': resposta, 'tools': chamadas})


@login_required
def agente_resumo_api(request, pk):
    """Resumo read-only de um agente (prompt + tools ativas) — pro nó ia_agente
    mostrar o que o agente escolhido faz, sem sair do editor."""
    neg = _exige_ver(request)
    if neg:
        return neg
    tenant = getattr(request, 'tenant', None)
    from .models import Agente
    from .services.ia_tools import tools_disponiveis
    ag = (Agente.all_tenants.filter(tenant=tenant, pk=pk)
          .select_related('integracao_ia').first())
    if ag is None:
        return JsonResponse({'erro': 'agente não encontrado'}, status=404)
    descr = {t['chave']: t['descricao'] for t in tools_disponiveis()}
    extras = getattr(ag.integracao_ia, 'configuracoes_extras', None) or {}
    cats = []
    if ag.base_categorias:
        from apps.suporte.models import CategoriaConhecimento
        cats = list(CategoriaConhecimento.all_tenants
                    .filter(tenant=tenant, pk__in=ag.base_categorias)
                    .values_list('nome', flat=True))
    return JsonResponse({
        'nome': ag.nome,
        'ativo': ag.ativo,
        'modelo': ag.modelo or extras.get('modelo', '') or '(default da integração)',
        'integracao': getattr(ag.integracao_ia, 'nome', '') or '',
        'system_prompt': ag.system_prompt or '',
        'tools': [{'chave': c, 'descricao': descr.get(c, '')} for c in (ag.tools or [])],
        'base_categorias': list(cats),
    })


@login_required
def nodes_catalogo_api(request):
    """Paleta: tipos de nó disponíveis pro editor montar a barra de blocos."""
    neg = _exige_ver(request)
    if neg:
        return neg
    return JsonResponse({'nodes': [
        {
            'tipo': n.tipo, 'label': n.label, 'icone': n.icone,
            'grupo': n.grupo, 'subgrupo': n.subgrupo, 'categoria': n.categoria,
            'saidas': n.saidas, 'is_trigger': n.is_trigger, 'campos': n.campos_config(),
            'saidas_dinamicas': n.saidas_dinamicas, 'campo_saidas': n.campo_saidas,
        }
        for n in REGISTRY.values()
    ]})


@require_POST
@login_required
def testar_fluxo_api(request):
    """Roda um fluxo postado pelo editor e devolve o trace. Não persiste nada."""
    neg = _exige_gerenciar(request)
    if neg:
        return neg
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
    if request.method == 'GET':
        neg = _exige_ver(request)
    else:
        neg = _exige_gerenciar(request)
    if neg:
        return neg

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
        try:
            registrar_acao('config', 'criar', 'fluxo', fluxo.id,
                            f"Fluxo '{fluxo.nome}' criado", request=request)
        except Exception:
            pass
        return JsonResponse({'id': fluxo.id, 'nome': fluxo.nome, 'webhook_token': token})

    return JsonResponse({'erro': 'método não suportado'}, status=405)


@login_required
def fluxo_api(request, pk):
    """Lê (GET), atualiza (PUT/POST) e remove (DELETE) um fluxo do tenant."""
    if request.method == 'GET':
        neg = _exige_ver(request)
    else:
        neg = _exige_gerenciar(request)
    if neg:
        return neg

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
        try:
            registrar_acao('config', 'editar', 'fluxo', fluxo.id,
                            f"Fluxo '{fluxo.nome}' atualizado", request=request)
        except Exception:
            pass
        return JsonResponse({'id': fluxo.id, 'nome': fluxo.nome, 'webhook_token': token})

    if request.method == 'DELETE':
        nome = fluxo.nome
        fid = fluxo.id
        fluxo.delete()
        try:
            registrar_acao('config', 'excluir', 'fluxo', fid,
                            f"Fluxo '{nome}' excluído", request=request)
        except Exception:
            pass
        return JsonResponse({'ok': True})

    return JsonResponse({'erro': 'método não suportado'}, status=405)


@require_POST
@login_required
def fluxo_webhook_api(request, pk):
    """Ativa o gatilho webhook do fluxo (gera token) e devolve a URL."""
    neg = _exige_gerenciar(request)
    if neg:
        return neg
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
    neg = _exige_ver(request)
    if neg:
        return neg
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
    try:
        contexto = Contexto(tenant=fluxo.tenant, variaveis={'payload': payload})
        execucao, res = executar_e_persistir(fluxo, contexto)
    except FluxoInvalido as exc:
        return JsonResponse({'erro': 'fluxo inválido', 'detalhes': str(exc)}, status=400)
    except Exception:
        logger.exception("Falha ao executar fluxo via webhook (token=%s)", token)
        return JsonResponse({'erro': 'falha interna ao executar o fluxo'}, status=500)

    # Modo de resposta (estilo n8n), configurado no próprio nó Webhook.
    grafo = fluxo.grafo or {}
    cfg_wh = ((grafo.get('nodes') or {}).get(grafo.get('inicio')) or {}).get('config') or {}
    modo = cfg_wh.get('responder') or 'imediato'

    # Um nó "Responder ao Webhook" (se rodou) sempre define a resposta.
    resp = (contexto.variaveis or {}).get('_resposta_webhook')
    if isinstance(resp, dict):
        corpo, status = resp.get('corpo', ''), resp.get('status', 200)
        try:
            return JsonResponse(json.loads(corpo), status=status, safe=False)
        except (ValueError, TypeError):
            return HttpResponse(corpo, status=status, content_type='text/plain; charset=utf-8')

    # "When Last Node Finishes": devolve o output do último nó executado.
    if modo == 'ultimo_no':
        passos = getattr(res, 'passos', None) or []
        ultimo = passos[-1].handle if passos else None
        return JsonResponse((contexto.nodes or {}).get(ultimo) or {}, safe=False)

    # "Immediately" (default): ack.
    return JsonResponse({'execucao_id': execucao.id, 'status': res.status})
