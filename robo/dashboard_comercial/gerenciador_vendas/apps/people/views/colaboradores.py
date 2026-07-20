"""
Cadastro de colaborador pelo RH.

A tela existe pra dar corpo aos tres pontos de entrada. A spec de origem
descrevia o ciclo como linear, mas o proprio produto tem um modal perguntando
"esse colaborador ja comecou a trabalhar?", com tres saidas que entram em fases
diferentes. Aqui as tres sao explicitas, e a situacao inicial vem do ponto de
entrada escolhido, nunca de um default escondido.

Nenhuma criacao acontece aqui: tudo passa por `registrar_colaborador`, que
pesquisa antes de criar. Quando ele acha alguem parecido, a tela pergunta em vez
de decidir sozinha.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.people import estados
from apps.people.forms import UFS, ColaboradorDadosForm, ColaboradorForm
from apps.people.models import (
    REGIME_CONTRATACAO_CHOICES, TIPO_CHAVE_PIX_CHOICES, Colaborador,
)
from apps.people.permissoes import pode_acessar, requer_people
from apps.people.services import marcar_revisado, registrar_colaborador
from apps.sistema.utils import registrar_acao


@requer_people('people.criar_colaborador')
def criar(request):
    entrada = request.GET.get('entrada') or estados.ENTRADA_SO_CADASTRO
    if entrada not in estados.PONTOS_ENTRADA or entrada == estados.ENTRADA_LINK_PUBLICO:
        entrada = estados.ENTRADA_SO_CADASTRO
    situacao_inicial = estados.situacao_de_entrada(entrada)

    form = ColaboradorForm(
        request.POST or None,
        tenant=request.tenant,
        situacao_inicial=situacao_inicial,
    )
    conflitos = []

    if request.method == 'POST' and form.is_valid():
        resultado = registrar_colaborador(
            request.tenant,
            form.cleaned_data['unidade'],
            form.dados_do_servico(),
            origem='rh',
            situacao_inicial=situacao_inicial,
            usuario=request.user,
            request=request,
            colaborador_id=request.POST.get('resolver_como') or None,
        )

        if resultado.ok:
            mensagens = {
                'criado': 'Colaborador cadastrado.',
                'reaproveitado': 'Ja existia um cadastro dessa pessoa. Os dados novos foram somados ao que ja havia.',
                'reativado': 'Essa pessoa ja trabalhou aqui. O cadastro dela foi reativado em vez de duplicado.',
            }
            messages.success(request, mensagens.get(resultado.acao, 'Cadastro salvo.'))
            return redirect('people:board')

        # Conflito: quem decide se e a mesma pessoa e o RH, nao o servico.
        conflitos = resultado.conflitos
        if resultado.motivo_conflito == 'nao_elegivel_recontratacao':
            messages.warning(
                request,
                'Essa pessoa foi marcada como nao elegivel a recontratacao. '
                'Ajuste na ficha dela antes de cadastrar de novo.',
            )

    return render(request, 'people/colaborador_form.html', {
        'pagetitle': 'Novo colaborador',
        'form': form,
        'entrada': entrada,
        'situacao_inicial': situacao_inicial,
        'rotulo_situacao': estados.rotulo(situacao_inicial),
        'conflitos': conflitos,
        # O componente de select recebe pares, nao queryset nem choices do form.
        'unidades_opcoes': list(
            form.fields['unidade'].queryset.values_list('pk', 'nome')),
        'regimes_opcoes': list(form.fields['regime_contratacao'].choices),
    })


@requer_people()
def detalhe(request, pk):
    """
    Ficha do colaborador. Tres abas: Resumo, Dados pessoais e Historico.

    A tela de origem tinha onze abas. Oito ficaram de fora de proposito: quatro
    pertencem a fases que ainda nao existem (checklist de admissao, documentos,
    envio de dados, desligamento) e quatro (Ocorrencias, Afastamentos, Atestados,
    Faltas) nenhuma fonte descreve o que fazem. Construir por adivinhacao seria
    inventar produto.
    """
    colaborador = get_object_or_404(
        Colaborador.objects.select_related('unidade', 'criado_por'), pk=pk)

    pode_editar = pode_acessar(request, 'people.criar_colaborador')
    form = ColaboradorDadosForm(
        request.POST or None,
        instance=colaborador,
    )

    if request.method == 'POST':
        if not pode_editar:
            messages.error(request, 'Sem permissao pra editar esta ficha.')
            return redirect('people:colaborador_detalhe', pk=pk)
        if form.is_valid():
            form.save()
            registrar_acao('people', 'editar', 'colaborador', colaborador.pk,
                           f'Dados de {colaborador.nome_completo} atualizados.',
                           request=request)
            messages.success(request, 'Dados salvos.')
            return redirect('people:colaborador_detalhe', pk=pk)

    historico = (colaborador.historico_situacao
                 .select_related('usuario')
                 .order_by('-criado_em'))

    return render(request, 'people/colaborador_detalhe.html', {
        'pagetitle': colaborador.nome_completo,
        'colaborador': colaborador,
        'form': form,
        'historico': historico,
        'pode_editar': pode_editar,
        'abas': [
            {'id': 'aba-resumo', 'label': 'Resumo', 'icon': 'bi-info-circle', 'active': True},
            {'id': 'aba-dados', 'label': 'Dados pessoais', 'icon': 'bi-person-vcard'},
            {'id': 'aba-historico', 'label': 'Histórico', 'icon': 'bi-clock-history',
             'badge': historico.count()},
        ],
        'ufs': UFS,
        'pix_opcoes': list(TIPO_CHAVE_PIX_CHOICES),
        'regimes_opcoes': [('', 'Nao definido')] + list(REGIME_CONTRATACAO_CHOICES),
        'destinos': [
            {'situacao': destino, 'rotulo': estados.rotulo(destino)}
            for destino in colaborador.destinos_possiveis
        ],
    })


@require_POST
@requer_people('people.criar_colaborador')
def revisar(request, pk):
    """Tira o colaborador da fila de revisao do RH."""
    colaborador = get_object_or_404(Colaborador.objects, pk=pk)
    marcar_revisado(colaborador, usuario=request.user)
    registrar_acao('people', 'validar', 'colaborador', colaborador.pk,
                   f'{colaborador.nome_completo} marcado como revisado.',
                   request=request)
    messages.success(request, 'Cadastro marcado como revisado.')
    return redirect('people:colaborador_detalhe', pk=pk)
