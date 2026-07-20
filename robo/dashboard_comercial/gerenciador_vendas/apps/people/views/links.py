"""
Tela "Cadastro via link": um cartao por unidade, com o link publico dela.

Espelha a tela de origem, onde cada loja tem seu cartao com Copiar Link, Baixar
QR, Desativar e Novo Link. O QR entra no passo seguinte.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.people.models import LinkCadastroUnidade, SubmissaoLinkCadastro, Unidade
from apps.people.permissoes import pode_acessar, requer_people
from apps.people.services import criar_link, desativar_link, rotacionar_link
from apps.sistema.utils import registrar_acao


@requer_people()
def lista(request):
    unidades = Unidade.objects.filter(ativo=True).order_by('nome')
    ativos = {
        link.unidade_id: link
        for link in LinkCadastroUnidade.objects.filter(ativo=True).select_related('unidade')
    }

    cartoes = [
        {
            'unidade': unidade,
            'link': ativos.get(unidade.pk),
            'url': request.build_absolute_uri(ativos[unidade.pk].caminho_publico)
                   if unidade.pk in ativos else '',
        }
        for unidade in unidades
    ]

    return render(request, 'people/links_lista.html', {
        'pagetitle': 'Cadastro via link',
        'cartoes': cartoes,
        'pode_gerir': pode_acessar(request, 'people.gerir_links'),
        'ultimas': (SubmissaoLinkCadastro.objects
                    .select_related('link__unidade', 'colaborador')[:15]),
    })


@require_POST
@requer_people('people.gerir_links')
def gerar(request, unidade_pk):
    unidade = get_object_or_404(Unidade.objects, pk=unidade_pk)
    link = criar_link(unidade, usuario=request.user)
    registrar_acao('people', 'criar', 'link_cadastro', link.pk,
                   f'Link de cadastro gerado para {unidade.nome}.', request=request)
    messages.success(request, f'Link de {unidade.nome} gerado.')
    return redirect('people:links_lista')


@require_POST
@requer_people('people.gerir_links')
def rotacionar(request, unidade_pk):
    """
    "Novo Link". Invalida o que esta circulando e poe outro no lugar.

    E a acao que se usa quando o link vazou pra fora da loja. Por isso a
    mensagem diz o que aconteceu com o antigo: quem clica precisa saber que
    acabou de quebrar o QR que esta na parede.
    """
    unidade = get_object_or_404(Unidade.objects, pk=unidade_pk)
    link = rotacionar_link(unidade, usuario=request.user)
    registrar_acao('people', 'editar', 'link_cadastro', link.pk,
                   f'Link de cadastro rotacionado para {unidade.nome}.', request=request)
    messages.success(
        request,
        f'Novo link de {unidade.nome} gerado. O anterior parou de funcionar, '
        f'entao redistribua o QR e o link de quem ja tinha o antigo.',
    )
    return redirect('people:links_lista')


@require_POST
@requer_people('people.gerir_links')
def desativar(request, unidade_pk):
    unidade = get_object_or_404(Unidade.objects, pk=unidade_pk)
    link = LinkCadastroUnidade.objects.filter(unidade=unidade, ativo=True).first()
    if link is None:
        messages.warning(request, f'{unidade.nome} nao tem link ativo.')
        return redirect('people:links_lista')

    desativar_link(link, usuario=request.user)
    registrar_acao('people', 'editar', 'link_cadastro', link.pk,
                   f'Link de cadastro desativado para {unidade.nome}.', request=request)
    messages.success(request, f'Link de {unidade.nome} desativado.')
    return redirect('people:links_lista')
