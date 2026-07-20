"""
Tela "Cadastro via link".

Lista de links, nao um cartao por loja: uma unidade pode ter varios links ativos
ao mesmo tempo, cada um com seu formulario e seu contador. Ver GAPS-VISIO.md,
gap 1.
"""
import io

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.people.models import (
    LinkCadastroUnidade, SubmissaoLinkCadastro, TemplateFormulario, Unidade,
)
from apps.people.permissoes import pode_acessar, requer_people
from apps.people.services import criar_link, desativar_link, reativar_link, rotacionar_link
from apps.sistema.utils import registrar_acao


@requer_people()
def lista(request):
    links = (LinkCadastroUnidade.objects
             .select_related('unidade', 'template')
             .order_by('-ativo', '-criado_em'))

    unidade_id = request.GET.get('unidade') or ''
    if unidade_id:
        links = links.filter(unidade_id=unidade_id)

    return render(request, 'people/links_lista.html', {
        'pagetitle': 'Cadastro via link',
        'links': [
            {'link': link, 'url': request.build_absolute_uri(link.caminho_publico)}
            for link in links
        ],
        'unidades_opcoes': list(
            Unidade.objects.filter(ativo=True).values_list('pk', 'nome')),
        'unidade_selecionada': unidade_id,
        'templates_opcoes': list(
            TemplateFormulario.objects.filter(ativo=True).values_list('pk', 'nome')),
        'pode_gerir': pode_acessar(request, 'people.gerir_links'),
        'ultimas': (SubmissaoLinkCadastro.objects
                    .select_related('link__unidade', 'colaborador')[:15]),
    })


@require_POST
@requer_people('people.gerir_links')
def criar(request):
    unidade = get_object_or_404(Unidade.objects, pk=request.POST.get('unidade'))
    template = None
    if request.POST.get('template'):
        template = TemplateFormulario.objects.filter(pk=request.POST['template']).first()

    link = criar_link(
        unidade, usuario=request.user,
        nome=(request.POST.get('nome') or '').strip(),
        template=template,
    )
    registrar_acao('people', 'criar', 'link_cadastro', link.pk,
                   f'Link de cadastro criado para {unidade.nome}.', request=request)
    messages.success(request, f'Link de {unidade.nome} criado.')
    return redirect('people:links_lista')


@require_POST
@requer_people('people.gerir_links')
def rotacionar(request, pk):
    """
    Invalida ESTE link e cria um substituto com a mesma configuracao.

    E a acao pra quando um link especifico vazou. Os outros links da mesma loja
    continuam valendo, que e a diferenca em relacao a desativar tudo.
    """
    link = get_object_or_404(LinkCadastroUnidade.objects, pk=pk)
    novo = rotacionar_link(link, usuario=request.user)
    registrar_acao('people', 'editar', 'link_cadastro', novo.pk,
                   f'Link rotacionado em {link.unidade.nome}.', request=request)
    messages.success(
        request,
        'Link substituido. O anterior parou de funcionar agora, entao redistribua '
        'o QR e o endereco pra quem tinha o antigo.',
    )
    return redirect('people:links_lista')


@requer_people()
def qr(request, pk):
    """
    QR do link, em SVG.

    SVG e nao PNG porque o uso real e cartaz colado na parede da loja: precisa
    escalar sem borrar na impressao. `segno` e pure python e nao arrasta Pillow.
    """
    import segno

    link = get_object_or_404(LinkCadastroUnidade.objects, pk=pk)
    url = request.build_absolute_uri(link.caminho_publico)

    buffer = io.BytesIO()
    segno.make(url, error='m').save(buffer, kind='svg', scale=8, border=2)

    resposta = HttpResponse(buffer.getvalue(), content_type='image/svg+xml')
    nome = link.unidade.codigo or 'unidade'
    resposta['Content-Disposition'] = f'attachment; filename="qr-{nome}.svg"'
    return resposta


@require_POST
@requer_people('people.gerir_links')
def alternar_ativo(request, pk):
    link = get_object_or_404(LinkCadastroUnidade.objects, pk=pk)
    if link.ativo:
        desativar_link(link, usuario=request.user)
        estado = 'desativado'
    else:
        reativar_link(link, usuario=request.user)
        estado = 'reativado'

    registrar_acao('people', 'editar', 'link_cadastro', link.pk,
                   f'Link {estado} em {link.unidade.nome}.', request=request)
    messages.success(request, f'Link {estado}.')
    return redirect('people:links_lista')
