"""
Cargos da empresa.

Cadastrados uma vez e reusados no cadastro de colaborador. Cargo nao se apaga
enquanto houver gente nele (PROTECT no Colaborador): apagar reescreveria
historico. Pra tirar de circulacao, desative.
"""
from django import forms
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.people import estados
from apps.people.models import Cargo
from apps.people.permissoes import pode_acessar, requer_people
from apps.sistema.utils import registrar_acao


class CargoForm(forms.ModelForm):
    class Meta:
        model = Cargo
        fields = ['nome', 'descricao', 'ordem', 'ativo']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant

    def clean_nome(self):
        """
        A unique do banco ja barraria, mas com IntegrityError na cara do
        usuario. Aqui vira mensagem no campo certo.
        """
        nome = ' '.join((self.cleaned_data.get('nome') or '').split())
        if not nome:
            return nome
        existentes = Cargo.all_tenants.filter(tenant=self.tenant, nome__iexact=nome)
        if self.instance and self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError('Ja existe um cargo com este nome.')
        return nome


@requer_people()
def lista(request):
    cargos = Cargo.objects.annotate(
        total_colaboradores=Count(
            'colaboradores',
            filter=Q(colaboradores__situacao__in=estados.SITUACOES_ATIVAS),
        ),
    ).order_by('-ativo', 'ordem', 'nome')

    return render(request, 'people/cargos_lista.html', {
        'pagetitle': 'Cargos',
        'cargos': cargos,
        'pode_gerir': pode_acessar(request, 'people.gerir_unidades'),
    })


@requer_people('people.gerir_unidades')
def criar(request):
    form = CargoForm(request.POST or None, tenant=request.tenant)

    if request.method == 'POST' and form.is_valid():
        cargo = form.save(commit=False)
        cargo.tenant = request.tenant
        cargo.save()
        registrar_acao('people', 'criar', 'cargo', cargo.pk,
                       f'Cargo "{cargo.nome}" criado.', request=request)
        messages.success(request, f'Cargo "{cargo.nome}" criado.')
        return redirect('people:cargos_lista')

    return render(request, 'people/cargo_form.html', {
        'pagetitle': 'Novo cargo', 'form': form, 'cargo': None,
    })


@requer_people('people.gerir_unidades')
def editar(request, pk):
    cargo = get_object_or_404(Cargo.objects, pk=pk)
    form = CargoForm(request.POST or None, instance=cargo, tenant=request.tenant)

    if request.method == 'POST' and form.is_valid():
        form.save()
        registrar_acao('people', 'editar', 'cargo', cargo.pk,
                       f'Cargo "{cargo.nome}" editado.', request=request)
        messages.success(request, f'Cargo "{cargo.nome}" salvo.')
        return redirect('people:cargos_lista')

    return render(request, 'people/cargo_form.html', {
        'pagetitle': cargo.nome, 'form': form, 'cargo': cargo,
    })


@require_POST
@requer_people('people.gerir_unidades')
def alternar_ativo(request, pk):
    """Nao existe excluir: colaborador aponta pro cargo com PROTECT."""
    cargo = get_object_or_404(Cargo.objects, pk=pk)
    cargo.ativo = not cargo.ativo
    cargo.save(update_fields=['ativo', 'atualizado_em'])

    estado = 'ativado' if cargo.ativo else 'desativado'
    registrar_acao('people', 'editar', 'cargo', cargo.pk,
                   f'Cargo "{cargo.nome}" {estado}.', request=request)
    messages.success(request, f'Cargo "{cargo.nome}" {estado}.')
    return redirect('people:cargos_lista')
