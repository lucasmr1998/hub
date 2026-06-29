"""Workspace — Agentes IA: roster + chat 1:1.

Reusa o motor do apps/automacao (nó ia_agente / chamar_llm_com_tools / ia_tools).
O endpoint de chat espelha o simulador do automacao, mas sob a permissao do
Workspace, pra feature ficar auto-suficiente (sem exigir acesso ao modulo automacao).
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade


@login_required
def lista(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden('Sem permissao pra acessar Workspace.')
    tenant = getattr(request, 'tenant', None)
    from apps.automacao.models import Agente
    agentes = []
    if tenant is not None:
        agentes = list(
            Agente.all_tenants.filter(tenant=tenant, ativo=True)
            .select_related('integracao_ia').order_by('equipe', 'ordem', 'nome')
        )
    return render(request, 'workspace/agentes.html', {
        'grupos': _agrupar_por_time(agentes),
        'total': len(agentes),
        'pode_editar': user_tem_funcionalidade(request, 'workspace.editar_todos'),
        'pagetitle': 'Agentes',
    })


def _agrupar_por_time(agentes):
    """Agrupa por time na ordem de EQUIPE_CHOICES; agentes 'sem time' por ultimo."""
    from apps.automacao.models import Agente
    labels = dict(Agente.EQUIPE_CHOICES)
    grupos = []
    for chave, label in Agente.EQUIPE_CHOICES:
        ags = [a for a in agentes if a.equipe == chave]
        if ags:
            grupos.append({'chave': chave, 'label': label, 'agentes': ags})
    sem_time = [a for a in agentes if a.equipe not in labels]
    if sem_time:
        grupos.append({'chave': '', 'label': 'Sem time / Outros', 'agentes': sem_time})
    return grupos


@require_POST
@login_required
def chat_api(request):
    """Chat 1:1 com um agente: roda o agente com as tools (de verdade), tenant-safe."""
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return JsonResponse({'erro': 'sem permissao'}, status=403)
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'sem tenant'}, status=400)

    from apps.automacao.models import Agente
    from apps.automacao.nodes import Contexto
    from apps.automacao.services.ia import chamar_llm, chamar_llm_com_tools, integracao_ia_do_tenant
    from apps.automacao.services.ia_tools import schema_openai, despachar

    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        data = {}
    mensagem = (data.get('mensagem') or '').strip()
    if not mensagem:
        return JsonResponse({'erro': 'mensagem vazia'}, status=400)
    agente = (Agente.all_tenants.filter(tenant=tenant, pk=data.get('agente_id'), ativo=True)
              .select_related('integracao_ia').first())
    if agente is None:
        return JsonResponse({'erro': 'agente nao encontrado'}, status=404)
    integracao = agente.integracao_ia or integracao_ia_do_tenant(tenant)
    if integracao is None:
        return JsonResponse({'erro': 'sem integracao de IA ativa no tenant'}, status=400)

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
        return JsonResponse({'erro': 'falha ao chamar o LLM (cheque a credencial/modelo)'}, status=502)
    return JsonResponse({'resposta': resposta, 'tools': chamadas})


# --- Editor (CRUD): gerencia o agente no workspace, reusando o model + tools_disponiveis ---

@login_required
def editar_page(request, pk=None):
    """Form de criar/editar um agente (todos os campos) + chat de teste ao lado."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return HttpResponseForbidden('Sem permissao pra gerenciar agentes.')
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return HttpResponseForbidden('sem tenant')
    from django.http import Http404
    from apps.automacao.models import Agente
    from apps.integracoes.models import IntegracaoAPI
    from apps.suporte.models import CategoriaConhecimento
    from apps.automacao.services.ia_tools import tools_disponiveis

    agente = None
    if pk:
        agente = (Agente.all_tenants.filter(tenant=tenant, pk=pk)
                  .select_related('integracao_ia').first())
        if agente is None:
            raise Http404('agente nao encontrado')
    integracoes = list(
        IntegracaoAPI.all_tenants
        .filter(tenant=tenant, tipo__in=['openai', 'anthropic', 'groq', 'google_ai'], ativa=True)
        .order_by('nome')
    )
    categorias = list(CategoriaConhecimento.all_tenants.filter(tenant=tenant).order_by('nome'))
    return render(request, 'workspace/agente_editar.html', {
        'agente': agente,
        'agente_tools': (agente.tools or []) if agente else [],
        'agente_cats': [str(x) for x in (agente.base_categorias or [])] if agente else [],
        'integracoes': integracoes,
        'categorias': categorias,
        'tools_disponiveis': sorted(tools_disponiveis(), key=lambda t: (t['categoria'], t['chave'])),
        'equipes': Agente.EQUIPE_CHOICES,
        'pagetitle': agente.nome if agente else 'Novo agente',
    })


@require_POST
@login_required
def salvar(request):
    """Cria/atualiza um agente do tenant (todos os campos, incl. organizacao por time)."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return JsonResponse({'erro': 'sem permissao'}, status=403)
    tenant = getattr(request, 'tenant', None)
    if tenant is None:
        return JsonResponse({'erro': 'sem tenant'}, status=400)
    from apps.automacao.models import Agente
    from apps.integracoes.models import IntegracaoAPI

    nome = (request.POST.get('nome') or '').strip()
    if not nome:
        return JsonResponse({'erro': 'nome obrigatorio'}, status=400)

    integracao = None
    integ_id = (request.POST.get('integracao_ia') or '').strip()
    if integ_id.isdigit():
        integracao = IntegracaoAPI.all_tenants.filter(tenant=tenant, id=int(integ_id)).first()

    pk = (request.POST.get('id') or '').strip()
    if pk.isdigit():
        agente = Agente.all_tenants.filter(tenant=tenant, pk=int(pk)).first()
        if agente is None:
            return JsonResponse({'erro': 'agente nao encontrado'}, status=404)
    else:
        agente = Agente(tenant=tenant,
                        criado_por=request.user if request.user.is_authenticated else None)

    equipes_validas = {k for k, _ in Agente.EQUIPE_CHOICES}
    equipe = (request.POST.get('equipe') or '').strip()
    agente.nome = nome
    agente.descricao = (request.POST.get('descricao') or '').strip()
    agente.equipe = equipe if equipe in equipes_validas else ''
    agente.cor = (request.POST.get('cor') or '').strip()[:7]
    agente.icone = (request.POST.get('icone') or '').strip()[:40] or 'bi-robot'
    agente.integracao_ia = integracao
    agente.modelo = (request.POST.get('modelo') or '').strip()
    agente.system_prompt = request.POST.get('system_prompt') or ''
    agente.prompt_autonomo = request.POST.get('prompt_autonomo') or ''
    agente.memoria = (request.POST.get('memoria') or 'conversa').strip()
    agente.ativo = (request.POST.get('ativo') or '') in ('on', 'true', '1')
    agente.tools = [t for t in request.POST.getlist('tools') if t]
    agente.base_categorias = [c for c in request.POST.getlist('base_categorias') if c]
    agente.save()
    return JsonResponse({'ok': True, 'id': agente.pk})


@require_POST
@login_required
def excluir(request, pk):
    """Remove um agente do tenant."""
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return JsonResponse({'erro': 'sem permissao'}, status=403)
    tenant = getattr(request, 'tenant', None)
    from apps.automacao.models import Agente
    agente = Agente.all_tenants.filter(tenant=tenant, pk=pk).first()
    if agente is None:
        return JsonResponse({'erro': 'agente nao encontrado'}, status=404)
    agente.delete()
    return JsonResponse({'ok': True})
