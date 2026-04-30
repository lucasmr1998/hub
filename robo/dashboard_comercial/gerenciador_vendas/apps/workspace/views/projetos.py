"""Views de Projeto + Etapa — CRUD completo + Kanban (estrutura)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.utils import registrar_acao
from apps.workspace.forms import EtapaForm, ProjetoForm
from apps.workspace.models import Etapa, Projeto


def _pode_editar(request, projeto):
    if request.user.is_superuser:
        return True
    if user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return True
    is_owner = (
        projeto.responsavel_id == request.user.id
        or any(t.responsavel_id == request.user.id for t in projeto.tarefas.all()[:1])
    )
    if is_owner and user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return True
    return False


# ============================================================================
# PROJETOS
# ============================================================================

@login_required
def lista(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()

    qs = Projeto.objects.select_related('responsavel').annotate(
        n_tarefas=Count('tarefas', distinct=True),
        n_concluidas=Count('tarefas', filter=Q(tarefas__status='concluida'), distinct=True),
    )

    status = request.GET.get('status', '').strip()
    busca = request.GET.get('q', '').strip()
    arquivados = request.GET.get('arquivados', '').strip()

    if status:
        qs = qs.filter(status=status)
    if busca:
        qs = qs.filter(Q(nome__icontains=busca) | Q(descricao__icontains=busca) | Q(objetivo__icontains=busca))
    if arquivados != '1':
        qs = qs.filter(ativo=True)

    ctx = {
        'projetos': qs.order_by('-criado_em')[:200],
        'status_choices': Projeto._meta.get_field('status').choices,
        'filtro_status': status,
        'busca': busca,
        'mostrar_arquivados': arquivados == '1',
        'pagetitle': 'Projetos',
    }
    return render(request, 'workspace/projetos/lista.html', ctx)


@login_required
def detalhe(request, pk):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()

    projeto = get_object_or_404(
        Projeto.objects.select_related('responsavel'),
        pk=pk,
    )
    etapas = projeto.etapas.annotate(
        n_tarefas=Count('tarefas'),
        n_concluidas=Count('tarefas', filter=Q(tarefas__status='concluida')),
    ).order_by('ordem', 'id')

    tarefas_por_status = {
        'pendente': projeto.tarefas.filter(status='pendente').count(),
        'em_andamento': projeto.tarefas.filter(status='em_andamento').count(),
        'concluida': projeto.tarefas.filter(status='concluida').count(),
        'bloqueada': projeto.tarefas.filter(status='bloqueada').count(),
    }

    ctx = {
        'projeto': projeto,
        'etapas': etapas,
        'tarefas_por_status': tarefas_por_status,
        'tarefas_recentes': projeto.tarefas.select_related('responsavel', 'etapa').order_by('-criado_em')[:8],
        'pode_editar': _pode_editar(request, projeto),
        'pagetitle': projeto.nome,
    }
    return render(request, 'workspace/projetos/detalhe.html', ctx)


@login_required
def criar(request):
    if not user_tem_funcionalidade(request, 'workspace.criar_projeto'):
        return HttpResponseForbidden('Sem permissao pra criar projetos.')
    tenant = getattr(request, 'tenant', None)
    if request.method == 'POST':
        form = ProjetoForm(request.POST, tenant=tenant)
        if form.is_valid():
            projeto = form.save(commit=False)
            projeto.tenant = tenant
            if not projeto.responsavel_id:
                projeto.responsavel = request.user
            projeto.save()
            registrar_acao('workspace', 'criar', 'projeto', projeto.id,
                f'Projeto "{projeto.nome}" criado', request=request)
            messages.success(request, 'Projeto criado.')
            return redirect('workspace:projeto_detalhe', pk=projeto.pk)
    else:
        form = ProjetoForm(tenant=tenant)
    return render(request, 'workspace/projetos/editar.html', {
        'form': form, 'projeto': None, 'pagetitle': 'Novo projeto',
    })


@login_required
def editar(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if not _pode_editar(request, projeto):
        return HttpResponseForbidden()
    tenant = getattr(request, 'tenant', None)
    if request.method == 'POST':
        form = ProjetoForm(request.POST, instance=projeto, tenant=tenant)
        if form.is_valid():
            form.save()
            registrar_acao('workspace', 'editar', 'projeto', projeto.id,
                f'Projeto "{projeto.nome}" atualizado', request=request)
            messages.success(request, 'Projeto atualizado.')
            return redirect('workspace:projeto_detalhe', pk=projeto.pk)
    else:
        form = ProjetoForm(instance=projeto, tenant=tenant)
    return render(request, 'workspace/projetos/editar.html', {
        'form': form, 'projeto': projeto, 'pagetitle': f'Editar: {projeto.nome}',
    })


@login_required
def excluir(request, pk):
    projeto = get_object_or_404(Projeto, pk=pk)
    if not user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return HttpResponseForbidden('Excluir projeto exige permissao de editar todos.')
    if request.method == 'POST':
        nome = projeto.nome
        n_tarefas = projeto.tarefas.count()
        projeto.delete()
        registrar_acao('workspace', 'excluir', 'projeto', pk,
            f'Projeto "{nome}" excluido (com {n_tarefas} tarefa(s) em cascata)', request=request)
        messages.success(request, f'Projeto "{nome}" excluido. {n_tarefas} tarefa(s) removida(s) em cascata.')
        return redirect('workspace:projetos_lista')
    return render(request, 'workspace/projetos/excluir.html', {'projeto': projeto})


@login_required
def kanban(request, pk):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()

    projeto = get_object_or_404(Projeto, pk=pk)
    pode_editar = _pode_editar(request, projeto)

    # Agrupa tarefas por status pra renderizar colunas
    tarefas_qs = projeto.tarefas.select_related('responsavel', 'etapa').order_by('ordem', '-criado_em')
    grupos = {
        'pendente': [],
        'em_andamento': [],
        'concluida': [],
        'bloqueada': [],
    }
    for t in tarefas_qs:
        if t.status in grupos:
            grupos[t.status].append(t)

    # Lista ordenada de colunas pra o template iterar
    colunas = [
        ('pendente', 'Pendente', grupos['pendente']),
        ('em_andamento', 'Em andamento', grupos['em_andamento']),
        ('concluida', 'Concluida', grupos['concluida']),
        ('bloqueada', 'Bloqueada', grupos['bloqueada']),
    ]

    ctx = {
        'projeto': projeto,
        'colunas': colunas,
        'etapas': projeto.etapas.order_by('ordem'),
        'pode_editar': pode_editar,
        'pagetitle': f'Kanban — {projeto.nome}',
    }
    return render(request, 'workspace/projetos/kanban.html', ctx)


# ============================================================================
# ETAPAS
# ============================================================================

@login_required
def etapa_criar(request, projeto_pk):
    projeto = get_object_or_404(Projeto, pk=projeto_pk)
    if not _pode_editar(request, projeto):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = EtapaForm(request.POST)
        if form.is_valid():
            etapa = form.save(commit=False)
            etapa.tenant = projeto.tenant
            etapa.projeto = projeto
            etapa.save()
            registrar_acao('workspace', 'criar', 'etapa', etapa.id,
                f'Etapa "{etapa.nome}" criada em "{projeto.nome}"', request=request)
            messages.success(request, 'Etapa criada.')
            return redirect('workspace:projeto_detalhe', pk=projeto.pk)
    else:
        form = EtapaForm()
    return render(request, 'workspace/projetos/etapa_editar.html', {
        'form': form, 'etapa': None, 'projeto': projeto, 'pagetitle': 'Nova etapa',
    })


@login_required
def etapa_editar(request, pk):
    etapa = get_object_or_404(Etapa, pk=pk)
    if not _pode_editar(request, etapa.projeto):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = EtapaForm(request.POST, instance=etapa)
        if form.is_valid():
            form.save()
            registrar_acao('workspace', 'editar', 'etapa', etapa.id,
                f'Etapa "{etapa.nome}" atualizada', request=request)
            messages.success(request, 'Etapa atualizada.')
            return redirect('workspace:projeto_detalhe', pk=etapa.projeto.pk)
    else:
        form = EtapaForm(instance=etapa)
    return render(request, 'workspace/projetos/etapa_editar.html', {
        'form': form, 'etapa': etapa, 'projeto': etapa.projeto, 'pagetitle': f'Editar: {etapa.nome}',
    })


@login_required
def etapa_excluir(request, pk):
    etapa = get_object_or_404(Etapa, pk=pk)
    if not _pode_editar(request, etapa.projeto):
        return HttpResponseForbidden()
    projeto_pk = etapa.projeto.pk
    if request.method == 'POST':
        nome = etapa.nome
        # Tarefas da etapa: ficam sem etapa (FK SET_NULL)
        etapa.tarefas.update(etapa=None)
        etapa.delete()
        registrar_acao('workspace', 'excluir', 'etapa', pk,
            f'Etapa "{nome}" excluida (tarefas mantidas no projeto)', request=request)
        messages.success(request, f'Etapa "{nome}" excluida.')
        return redirect('workspace:projeto_detalhe', pk=projeto_pk)
    return render(request, 'workspace/projetos/etapa_excluir.html', {'etapa': etapa})
