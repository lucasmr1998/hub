"""
Unidades (lojas e filiais).

Unidade nao se apaga: ela e desativada. Colaborador aponta pra ela com PROTECT,
e apagar uma loja com gente dentro orfanaria o cadastro. Desativada, ela some
das listas de escolha e preserva todo o historico.
"""
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.people import estados
from apps.people.forms import HERANCA_CHOICES, UFS, UnidadeForm
from apps.people.models import Unidade
from apps.people.permissoes import pode_acessar, requer_people
from apps.sistema.utils import registrar_acao


@requer_people()
def lista(request):
    unidades = Unidade.objects.annotate(
        total_colaboradores=Count(
            'colaboradores',
            filter=Q(colaboradores__situacao__in=estados.SITUACOES_ATIVAS),
        ),
    ).order_by('-ativo', 'nome')

    contexto = {
        'pagetitle': 'Unidades',
        'unidades': unidades,
        'pode_gerir': pode_acessar(request, 'people.gerir_unidades'),
    }
    return render(request, 'people/unidades_lista.html', contexto)


@requer_people('people.gerir_unidades')
def criar(request):
    form = UnidadeForm(request.POST or None, tenant=request.tenant)

    if request.method == 'POST' and form.is_valid():
        unidade = form.save(commit=False)
        unidade.tenant = request.tenant
        unidade.save()
        registrar_acao('people', 'criar', 'unidade', unidade.pk,
                       f'Unidade "{unidade.nome}" criada.', request=request)
        messages.success(request, f'Unidade "{unidade.nome}" criada.')
        return redirect('people:unidades_lista')

    return render(request, 'people/unidade_form.html', {
        'pagetitle': 'Nova unidade',
        'form': form,
        'ufs': UFS,
        'heranca_choices': HERANCA_CHOICES,
        'unidade': None,
    })


@requer_people('people.gerir_unidades')
def editar(request, pk):
    unidade = get_object_or_404(Unidade.objects, pk=pk)
    form = UnidadeForm(request.POST or None, instance=unidade, tenant=request.tenant)

    if request.method == 'POST' and form.is_valid():
        form.save()
        registrar_acao('people', 'editar', 'unidade', unidade.pk,
                       f'Unidade "{unidade.nome}" editada.', request=request)
        messages.success(request, f'Unidade "{unidade.nome}" salva.')
        return redirect('people:unidades_lista')

    return render(request, 'people/unidade_form.html', {
        'pagetitle': unidade.nome,
        'form': form,
        'ufs': UFS,
        'heranca_choices': HERANCA_CHOICES,
        'unidade': unidade,
    })


@require_POST
@requer_people('people.gerir_unidades')
def alternar_ativo(request, pk):
    """
    Ativa ou desativa. Nao existe excluir: colaborador aponta pra unidade com
    PROTECT, e a trilha do historico depende dela continuar existindo.
    """
    unidade = get_object_or_404(Unidade.objects, pk=pk)
    unidade.ativo = not unidade.ativo
    unidade.save(update_fields=['ativo', 'atualizado_em'])

    estado = 'ativada' if unidade.ativo else 'desativada'
    registrar_acao('people', 'editar', 'unidade', unidade.pk,
                   f'Unidade "{unidade.nome}" {estado}.', request=request)
    messages.success(request, f'Unidade "{unidade.nome}" {estado}.')
    return redirect('people:unidades_lista')
