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
from django.shortcuts import redirect, render

from apps.people import estados
from apps.people.forms import ColaboradorForm
from apps.people.permissoes import requer_people
from apps.people.services import registrar_colaborador


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
