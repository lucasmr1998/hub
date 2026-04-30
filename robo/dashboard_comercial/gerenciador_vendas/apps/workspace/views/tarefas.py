"""Views de Tarefa + Nota — CRUD completo + visao 'minhas tarefas'."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.utils import registrar_acao
from apps.workspace.forms import NotaForm, TarefaForm
from apps.workspace.models import Nota, Projeto, Tarefa


def _pode_editar(request, tarefa):
    if request.user.is_superuser:
        return True
    if user_tem_funcionalidade(request, 'workspace.editar_todos'):
        return True
    is_owner = tarefa.responsavel_id == request.user.id or tarefa.projeto.responsavel_id == request.user.id
    if is_owner and user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return True
    return False


# ============================================================================
# MINHAS TAREFAS — visao cross-projeto
# ============================================================================

@login_required
def minhas(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()

    qs = Tarefa.objects.select_related('projeto', 'etapa', 'responsavel')

    escopo = request.GET.get('escopo', 'minhas')
    status = request.GET.get('status', '').strip()
    prioridade = request.GET.get('prioridade', '').strip()
    busca = request.GET.get('q', '').strip()

    if escopo == 'minhas':
        qs = qs.filter(responsavel=request.user)
    elif escopo == 'criadas':
        # Tarefas em projetos onde sou responsavel
        qs = qs.filter(projeto__responsavel=request.user)
    # escopo == 'todas': sem filtro adicional (precisa editar_todos pra fazer sentido)

    if status:
        qs = qs.filter(status=status)
    else:
        # Default: esconde concluidas
        qs = qs.exclude(status='concluida')

    if prioridade:
        qs = qs.filter(prioridade=prioridade)
    if busca:
        qs = qs.filter(Q(titulo__icontains=busca) | Q(descricao__icontains=busca))

    # Buckets de prazo
    hoje = timezone.now().date()
    em_7_dias = hoje + timezone.timedelta(days=7)

    atrasadas = qs.filter(data_limite__lt=hoje).order_by('data_limite')
    hoje_qs = qs.filter(data_limite=hoje)
    proximas = qs.filter(data_limite__gt=hoje, data_limite__lte=em_7_dias).order_by('data_limite')
    sem_prazo = qs.filter(data_limite__isnull=True).order_by('-criado_em')[:50]
    futuras = qs.filter(data_limite__gt=em_7_dias).order_by('data_limite')[:30]

    ctx = {
        'escopo': escopo,
        'atrasadas': atrasadas,
        'hoje': hoje_qs,
        'proximas': proximas,
        'sem_prazo': sem_prazo,
        'futuras': futuras,
        'status_choices': Tarefa._meta.get_field('status').choices,
        'prioridade_choices': Tarefa._meta.get_field('prioridade').choices,
        'filtro_status': status,
        'filtro_prioridade': prioridade,
        'busca': busca,
        'pagetitle': 'Minhas tarefas',
    }
    return render(request, 'workspace/tarefas/lista.html', ctx)


# ============================================================================
# DETALHE DE TAREFA + NOTAS INLINE
# ============================================================================

@login_required
def detalhe(request, pk):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()
    tarefa = get_object_or_404(
        Tarefa.objects.select_related('projeto', 'etapa', 'responsavel'),
        pk=pk,
    )
    notas = tarefa.notas.select_related('autor').order_by('criado_em')
    pode_editar = _pode_editar(request, tarefa)
    nota_form = NotaForm()
    ctx = {
        'tarefa': tarefa,
        'notas': notas,
        'pode_editar': pode_editar,
        'nota_form': nota_form,
        'pagetitle': tarefa.titulo,
    }
    return render(request, 'workspace/tarefas/detalhe.html', ctx)


@login_required
def criar(request, projeto_pk):
    projeto = get_object_or_404(Projeto, pk=projeto_pk)
    if not user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return HttpResponseForbidden()
    tenant = getattr(request, 'tenant', None)
    if request.method == 'POST':
        form = TarefaForm(request.POST, tenant=tenant, projeto=projeto)
        if form.is_valid():
            tarefa = form.save(commit=False)
            tarefa.tenant = tenant
            tarefa.projeto = projeto
            if not tarefa.responsavel_id:
                tarefa.responsavel = request.user
            tarefa.save()
            registrar_acao('workspace', 'criar', 'tarefa', tarefa.id,
                f'Tarefa "{tarefa.titulo}" criada em "{projeto.nome}"', request=request)
            messages.success(request, 'Tarefa criada.')
            return redirect('workspace:tarefa_detalhe', pk=tarefa.pk)
    else:
        form = TarefaForm(tenant=tenant, projeto=projeto)
    return render(request, 'workspace/tarefas/editar.html', {
        'form': form, 'tarefa': None, 'projeto': projeto, 'pagetitle': 'Nova tarefa',
    })


@login_required
def editar(request, pk):
    tarefa = get_object_or_404(Tarefa, pk=pk)
    if not _pode_editar(request, tarefa):
        return HttpResponseForbidden()
    tenant = getattr(request, 'tenant', None)
    if request.method == 'POST':
        form = TarefaForm(request.POST, instance=tarefa, tenant=tenant, projeto=tarefa.projeto)
        if form.is_valid():
            old_status = Tarefa.objects.get(pk=tarefa.pk).status
            t = form.save(commit=False)
            # Se mudou pra concluida, marcar data_conclusao
            if t.status == 'concluida' and old_status != 'concluida':
                t.data_conclusao = timezone.now()
            elif t.status != 'concluida':
                t.data_conclusao = None
            t.save()
            registrar_acao('workspace', 'editar', 'tarefa', tarefa.id,
                f'Tarefa "{tarefa.titulo}" atualizada (status: {old_status} -> {t.status})', request=request)
            messages.success(request, 'Tarefa atualizada.')
            return redirect('workspace:tarefa_detalhe', pk=tarefa.pk)
    else:
        form = TarefaForm(instance=tarefa, tenant=tenant, projeto=tarefa.projeto)
    return render(request, 'workspace/tarefas/editar.html', {
        'form': form, 'tarefa': tarefa, 'projeto': tarefa.projeto, 'pagetitle': f'Editar: {tarefa.titulo}',
    })


@login_required
def excluir(request, pk):
    tarefa = get_object_or_404(Tarefa, pk=pk)
    if not _pode_editar(request, tarefa):
        return HttpResponseForbidden()
    projeto_pk = tarefa.projeto.pk
    if request.method == 'POST':
        titulo = tarefa.titulo
        n_notas = tarefa.notas.count()
        tarefa.delete()
        registrar_acao('workspace', 'excluir', 'tarefa', pk,
            f'Tarefa "{titulo}" excluida ({n_notas} nota(s) em cascata)', request=request)
        messages.success(request, f'Tarefa "{titulo}" excluida.')
        return redirect('workspace:projeto_detalhe', pk=projeto_pk)
    return render(request, 'workspace/tarefas/excluir.html', {'tarefa': tarefa})


# ============================================================================
# NOTAS
# ============================================================================

@login_required
def nota_criar(request, tarefa_pk):
    tarefa = get_object_or_404(Tarefa, pk=tarefa_pk)
    if not user_tem_funcionalidade(request, 'workspace.editar_proprios'):
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = NotaForm(request.POST)
        if form.is_valid():
            nota = form.save(commit=False)
            nota.tenant = tarefa.tenant
            nota.tarefa = tarefa
            nota.autor = request.user
            nota.save()
            registrar_acao('workspace', 'criar', 'nota', nota.id,
                f'Nota adicionada em "{tarefa.titulo}"', request=request)
            messages.success(request, 'Nota adicionada.')
    return redirect('workspace:tarefa_detalhe', pk=tarefa.pk)


@login_required
def nota_excluir(request, pk):
    nota = get_object_or_404(Nota, pk=pk)
    # Pode excluir se: superuser OU autor da nota OU editar_todos
    pode = (
        request.user.is_superuser
        or nota.autor_id == request.user.id
        or user_tem_funcionalidade(request, 'workspace.editar_todos')
    )
    if not pode:
        return HttpResponseForbidden()
    tarefa_pk = nota.tarefa.pk
    if request.method == 'POST':
        nota.delete()
        registrar_acao('workspace', 'excluir', 'nota', pk,
            'Nota excluida', request=request)
        messages.success(request, 'Nota excluida.')
    return redirect('workspace:tarefa_detalhe', pk=tarefa_pk)
