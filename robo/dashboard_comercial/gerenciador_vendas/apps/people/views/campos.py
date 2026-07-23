"""
Campos de candidatura que o tenant inventa.

O catalogo de `campos_candidatura.py` e fixo em codigo porque cada campo de la
tem coluna no Candidato. Esta tela e a saida pro que nao tem coluna: CNH, curso,
o que a operacao pedir, sem migration em producao.

DIVISAO DE PAPEL, a mesma dos campos de sistema: aqui o tenant DEFINE o campo
(rotulo, tipo, opcoes); na vaga ele escolhe se pede e se e obrigatorio. Sem essa
divisao seriam dois modelos mentais pra mesma tabela de configuracao.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.people import campos_candidatura as catalogo
from apps.people.models import CampoCandidatura, Candidato
from apps.people.permissoes import requer_people
from apps.sistema.utils import registrar_acao


def _voltar():
    # Aba Campos do hub de Configuracoes. Client-side, entao o `?tab=` diz ao JS
    # qual painel reabrir depois do POST.
    return redirect('/people/fluxo/?tab=campos')


def _slug_livre(tenant, base, ignorar_pk=None):
    """
    Slug unico no tenant, com sufixo numerico quando o obvio ja existe.

    A unique do banco barraria de qualquer jeito, mas com IntegrityError na cara
    do usuario. E devolver "ja existe, escolha outro nome" pra um campo chamado
    "Turno" so porque um campo desativado ocupa o slug seria pior ainda.
    """
    base = slugify(base).replace('-', '_')[:50] or 'campo'
    candidato = base
    sufixo = 2
    while True:
        existe = CampoCandidatura.all_tenants.filter(tenant=tenant,
                                                     slug=candidato)
        if ignorar_pk:
            existe = existe.exclude(pk=ignorar_pk)
        if not existe.exists():
            return candidato
        candidato = f'{base}_{sufixo}'
        sufixo += 1


def _ler_opcoes(bruto):
    """Uma opcao por linha, sem vazias e sem repetida."""
    vistas = []
    for linha in (bruto or '').splitlines():
        texto = ' '.join(linha.split())
        if texto and texto not in vistas:
            vistas.append(texto)
    return vistas


@requer_people()
def contexto_campos(request):
    """
    Contexto da aba Campos, namespaceado com prefixo `campos_`.

    Separado da view porque quem monta a tela e o hub de Configuracoes
    (`fluxo.configurar`), que junta quatro abas. Chave generica como `linhas`
    colidiria com a das Etapas; o prefixo resolve.
    """
    campos = list(CampoCandidatura.objects.all().order_by('ordem', 'nome'))

    # Quantos candidatos ja responderam cada campo. E o que a tela precisa pra
    # avisar antes de apagar: apagar o campo apaga a pergunta, nao a resposta,
    # e a resposta vira dado orfao no JSON que ninguem mais sabe ler.
    respostas = {campo.slug: 0 for campo in campos}
    for dados in Candidato.objects.exclude(dados_custom={}).values_list(
            'dados_custom', flat=True):
        for slug in (dados or {}):
            if slug in respostas:
                respostas[slug] += 1

    return {
        'campos_linhas': [{'campo': campo, 'respostas': respostas.get(campo.slug, 0)}
                          for campo in campos],
        'campos_tipos': CampoCandidatura.TIPO_CHOICES,
        'campos_secoes': [(s['chave'], s['titulo']) for s in catalogo.SECOES],
        'campos_sistema': catalogo.CAMPOS_SISTEMA,
    }


def configurar(request):
    """Rota antiga: a tela virou aba do hub de Configuracoes."""
    return redirect('/people/fluxo/?tab=campos')


@require_POST
@requer_people('people.gerir_vagas')
def salvar(request):
    """Cria ou edita um campo. Um handler so, porque o formulario e o mesmo."""
    pk = (request.POST.get('pk') or '').strip()
    nome = ' '.join((request.POST.get('nome') or '').split())
    tipo = (request.POST.get('tipo') or 'text').strip()
    secao = (request.POST.get('secao') or 'experiencia').strip()
    ajuda = ' '.join((request.POST.get('ajuda') or '').split())
    opcoes = _ler_opcoes(request.POST.get('opcoes'))

    if not nome:
        messages.error(request, 'O campo precisa de um rótulo.')
        return _voltar()

    if tipo not in dict(CampoCandidatura.TIPO_CHOICES):
        messages.error(request, 'Tipo de campo inválido.')
        return _voltar()

    if tipo == 'select' and not opcoes:
        messages.error(request, 'Um campo de lista precisa de pelo menos uma '
                                'opção.')
        return _voltar()

    if secao not in {s['chave'] for s in catalogo.SECOES}:
        secao = 'experiencia'

    dados = {
        'nome': nome,
        'tipo': tipo,
        'secao': secao,
        'ajuda': ajuda[:200],
        'opcoes': opcoes if tipo == 'select' else [],
    }

    if pk.isdigit():
        campo = get_object_or_404(CampoCandidatura.objects, pk=int(pk))
        # O SLUG NAO MUDA na edicao. Ele e a chave das respostas ja gravadas em
        # `dados_custom`; trocar deixaria toda resposta anterior orfa, sem erro
        # nenhum, so um campo que aparece vazio pra quem ja respondeu.
        for atributo, valor in dados.items():
            setattr(campo, atributo, valor)
        campo.save()
        acao = 'editado'
    else:
        ultimo = CampoCandidatura.objects.order_by('-ordem').first()
        campo = CampoCandidatura.all_tenants.create(
            tenant=request.tenant,
            slug=_slug_livre(request.tenant, nome),
            ordem=(ultimo.ordem + 1) if ultimo else 1,
            ativo=True, **dados)
        acao = 'criado'

    registrar_acao('people', 'editar', 'campo_candidatura', campo.pk,
                   f'Campo "{campo.nome}" {acao}.', request=request)
    messages.success(
        request,
        f'Campo "{campo.nome}" {acao}. Ligue ele nas vagas que devem pedi-lo.'
        if acao == 'criado' else f'Campo "{campo.nome}" {acao}.')
    return _voltar()


@require_POST
@requer_people('people.gerir_vagas')
def alternar(request, pk):
    """
    Liga e desliga o campo.

    Desativar tira o campo dos formularios sem apagar o que ja foi respondido.
    E o caminho pra parar de perguntar algo sem perder o historico, que apagar
    nao oferece.
    """
    campo = get_object_or_404(CampoCandidatura.objects, pk=pk)
    campo.ativo = not campo.ativo
    campo.save(update_fields=['ativo', 'atualizado_em'])

    estado = 'ativado' if campo.ativo else 'desativado'
    registrar_acao('people', 'editar', 'campo_candidatura', campo.pk,
                   f'Campo "{campo.nome}" {estado}.', request=request)
    messages.success(request, f'Campo "{campo.nome}" {estado}.')
    return _voltar()


@require_POST
@requer_people('people.gerir_vagas')
def mover(request, pk):
    """Troca a ordem com o campo vizinho."""
    campo = get_object_or_404(CampoCandidatura.objects, pk=pk)
    direcao = request.POST.get('direcao')

    irmaos = list(CampoCandidatura.objects.all().order_by('ordem', 'nome'))
    posicao = next((i for i, c in enumerate(irmaos) if c.pk == campo.pk), None)
    destino = posicao - 1 if direcao == 'cima' else posicao + 1

    if posicao is None or not (0 <= destino < len(irmaos)):
        return _voltar()   # ja esta na ponta, nao e erro

    vizinho = irmaos[destino]
    campo.ordem, vizinho.ordem = vizinho.ordem, campo.ordem
    campo.save(update_fields=['ordem'])
    vizinho.save(update_fields=['ordem'])
    return _voltar()


@require_POST
@requer_people('people.gerir_vagas')
def remover(request, pk):
    """
    Apaga o campo, e SO se ninguem tiver respondido.

    Com resposta gravada, apagar deixaria o valor no `dados_custom` de cada
    candidato sem nada que diga o que aquela chave significava: dado orfao que
    ninguem consegue mais ler. Pra parar de perguntar, o caminho e desativar.
    """
    campo = get_object_or_404(CampoCandidatura.objects, pk=pk)

    # Contagem em Python, e nao com lookup `dados_custom__<slug>`: o slug vem de
    # texto do usuario e montar o nome do lookup por f-string faria a consulta
    # depender do que ele digitou. Um lookup que erra a chave devolveria zero, e
    # zero aqui LIBERA o apagar. Errar pro lado que apaga dado nao serve.
    respondido = sum(
        1 for dados in Candidato.objects.exclude(dados_custom={}).values_list(
            'dados_custom', flat=True)
        if campo.slug in (dados or {}))
    if respondido:
        messages.error(
            request,
            f'{respondido} candidato(s) já responderam "{campo.nome}". Apagar '
            f'deixaria essas respostas ilegíveis. Use Desativar.')
        return _voltar()

    nome = campo.nome
    campo.delete()
    registrar_acao('people', 'excluir', 'campo_candidatura', pk,
                   f'Campo "{nome}" removido (sem respostas).', request=request)
    messages.success(request, f'Campo "{nome}" removido.')
    return _voltar()
