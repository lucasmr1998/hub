"""
Quadro por unidade: quantas posicoes de cada cargo a loja quer ter.

E a moldura contra a qual o recrutamento e lido. Sem quadro, vaga aberta e um
numero solto; com quadro, vira "faltam 2 de 8". Os derivados (ativos, em
processo) sao calculados na hora, nunca guardados: contagem em coluna e o
caminho mais curto pra divergir do real.
"""
from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.people.models import Cargo, QuadroUnidade, Unidade
from apps.people.permissoes import requer_people
from apps.sistema.utils import registrar_acao


class QuadroForm(forms.ModelForm):
    class Meta:
        model = QuadroUnidade
        fields = ['unidade', 'cargo', 'quadro_definido']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        # So o que e do tenant nos selects, senao um POST forjado apontaria
        # pra unidade ou cargo de outro cliente.
        self.fields['unidade'].queryset = Unidade.all_tenants.filter(
            tenant=tenant, ativo=True).order_by('nome')
        self.fields['cargo'].queryset = Cargo.all_tenants.filter(
            tenant=tenant, ativo=True).order_by('ordem', 'nome')
        self.fields['unidade'].empty_label = 'Selecione'
        self.fields['cargo'].empty_label = 'Selecione'

    def clean(self):
        dados = super().clean()
        unidade = dados.get('unidade')
        cargo = dados.get('cargo')
        if unidade and cargo:
            existe = QuadroUnidade.all_tenants.filter(
                tenant=self.tenant, unidade=unidade, cargo=cargo)
            if self.instance and self.instance.pk:
                existe = existe.exclude(pk=self.instance.pk)
            if existe.exists():
                raise forms.ValidationError(
                    'Já existe quadro para este cargo nesta unidade. Edite o '
                    'que já existe.')
        return dados


def _voltar():
    # Aba Quadro do hub de Configuracoes. O ?tab= diz ao JS qual painel reabrir
    # depois do POST.
    return redirect('/people/fluxo/?tab=quadro')


def contexto_quadro(request, unidade):
    """
    Contexto da aba Quadro, namespaceado com prefixo `quadro_`.

    Recebe o `unidade` (objeto ou None) do hub, o MESMO que escopa Etapas e
    Mensagens: um seletor de unidade so no header controla as tres. Sem unidade,
    lista o quadro de todas.
    """
    quadros = (QuadroUnidade.objects
               .select_related('unidade', 'cargo')
               .order_by('unidade__nome', 'cargo__nome'))
    if unidade:
        quadros = quadros.filter(unidade=unidade)

    return {
        'quadro_linhas': [{'quadro': q, 'situacao': q.situacao()} for q in quadros],
        'quadro_form': QuadroForm(tenant=request.tenant),
    }


def lista(request):
    """Rota antiga: a tela virou aba do hub de Configuracoes."""
    return redirect('/people/fluxo/?tab=quadro')


@require_POST
@requer_people('people.gerir_vagas')
def salvar(request):
    form = QuadroForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        for erros in form.errors.values():
            for erro in erros:
                messages.error(request, erro)
        return _voltar()

    quadro = form.save(commit=False)
    quadro.tenant = request.tenant
    quadro.save()
    registrar_acao('people', 'editar', 'quadro_unidade', quadro.pk,
                   f'Quadro de {quadro.cargo.nome} em {quadro.unidade.nome} '
                   f'definido em {quadro.quadro_definido}.', request=request)
    messages.success(request, 'Quadro salvo.')
    return _voltar()


@require_POST
@requer_people('people.gerir_vagas')
def remover(request, pk):
    quadro = get_object_or_404(QuadroUnidade.objects, pk=pk)
    quadro.delete()
    messages.success(request, 'Quadro removido.')
    return _voltar()
