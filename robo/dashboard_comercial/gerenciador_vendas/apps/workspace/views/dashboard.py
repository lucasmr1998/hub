"""Workspace home — visão executiva: projetos ativos, tarefas urgentes, docs recentes."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from apps.sistema.decorators import user_tem_funcionalidade
from apps.workspace.models import Documento, Projeto, Tarefa


@login_required
def home(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden('Sem permissão pra acessar Workspace.')

    hoje = timezone.now().date()
    em_7_dias = hoje + timezone.timedelta(days=7)

    projetos_ativos = Projeto.objects.filter(ativo=True, status__in=['planejamento', 'em_andamento']).order_by('-criado_em')[:8]
    tarefas_urgentes = Tarefa.objects.filter(
        status__in=['pendente', 'em_andamento'],
        data_limite__lte=em_7_dias,
    ).order_by('data_limite', 'prioridade')[:10]
    docs_recentes = Documento.objects.order_by('-atualizado_em')[:6]

    ctx = {
        'projetos_ativos': projetos_ativos,
        'tarefas_urgentes': tarefas_urgentes,
        'docs_recentes': docs_recentes,
        'total_projetos': Projeto.objects.filter(ativo=True).count(),
        'total_tarefas_pendentes': Tarefa.objects.filter(status__in=['pendente', 'em_andamento']).count(),
        'total_docs': Documento.objects.count(),
        'pagetitle': 'Workspace',
    }
    return render(request, 'workspace/home.html', ctx)
