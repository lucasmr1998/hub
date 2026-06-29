"""Workspace — Propostas: fila de aprovacao humana das acoes propostas pelos agentes.

V1: advisory (aprovar/rejeitar registra a decisao). A execucao diferida do
`dados_execucao` ao aprovar fica pro proximo incremento.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade
from apps.workspace.models import Proposta


def _pode_decidir(request):
    return request.user.is_superuser or user_tem_funcionalidade(request, 'workspace.editar_todos')


@login_required
def lista(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden('Sem permissao pra acessar Workspace.')
    pendentes = list(
        Proposta.objects.filter(status='pendente')
        .select_related('agente', 'tarefa').order_by('-criado_em')
    )
    decididas = list(
        Proposta.objects.exclude(status='pendente')
        .select_related('agente', 'decidido_por').order_by('-data_decisao', '-criado_em')[:30]
    )
    return render(request, 'workspace/propostas.html', {
        'pendentes': pendentes,
        'decididas': decididas,
        'pode_decidir': _pode_decidir(request),
        'pagetitle': 'Propostas',
    })


@require_POST
@login_required
def decidir(request, pk):
    if not _pode_decidir(request):
        return HttpResponseForbidden('Sem permissao pra decidir propostas.')
    p = Proposta.objects.filter(pk=pk, status='pendente').first()
    if p is None:
        return redirect('workspace:propostas_lista')
    acao = (request.POST.get('acao') or '').strip()
    if acao == 'aprovar':
        p.status = 'aprovada'
        p.decidido_por = request.user
        p.data_decisao = timezone.now()
        p.save(update_fields=['status', 'decidido_por', 'data_decisao'])
    elif acao == 'rejeitar':
        p.status = 'rejeitada'
        p.decidido_por = request.user
        p.data_decisao = timezone.now()
        p.motivo_rejeicao = (request.POST.get('motivo') or '').strip()
        p.save(update_fields=['status', 'decidido_por', 'data_decisao', 'motivo_rejeicao'])
    return redirect('workspace:propostas_lista')
