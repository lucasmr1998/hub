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
            .select_related('integracao_ia').order_by('nome')
        )
    return render(request, 'workspace/agentes.html', {
        'agentes': agentes,
        'pagetitle': 'Agentes',
    })


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
