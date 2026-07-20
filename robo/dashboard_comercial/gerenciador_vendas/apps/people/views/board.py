"""
Board do ciclo de vida do colaborador.

Uma coluna por fase, card por pessoa, e o arrasto e a unica forma de mudar de
fase pela UI. O endpoint de mover nao decide nada: delega pra
`mover_situacao()`, que valida a transicao contra a maquina de estados.

Quando a transicao exige campo que ainda nao existe (entrar em admissao sem data
de admissao, por exemplo), o endpoint devolve 400 dizendo QUAIS campos faltam, e
a interface pergunta em vez de simplesmente recusar. Recusar sem explicar e o
que faz o gestor perder a confianca na tela.
"""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.people import estados
from apps.people.consultas import contagem_por_situacao
from apps.people.excecoes import CampoObrigatorioFaltando, TransicaoInvalida
from apps.people.models import Colaborador, Unidade
from apps.people.permissoes import pode_acessar, requer_people
from apps.people.services import mover_situacao


# Como pedir cada campo que uma transicao pode exigir. `tipo` vira o type do
# input no modal, entao data vira date picker em vez de texto livre.
CAMPOS_DA_TRANSICAO = {
    'data_admissao':       {'label': 'Data de admissao', 'tipo': 'date'},
    'data_desligamento':   {'label': 'Data de desligamento', 'tipo': 'date'},
    'motivo_desligamento': {'label': 'Motivo do desligamento', 'tipo': 'text'},
}


@requer_people()
def board(request):
    unidade_id = request.GET.get('unidade') or ''
    colaboradores = (
        Colaborador.objects
        .select_related('unidade')
        .order_by('nome_completo')
    )
    if unidade_id:
        colaboradores = colaboradores.filter(unidade_id=unidade_id)

    unidade_filtro = None
    if unidade_id:
        unidade_filtro = Unidade.objects.filter(pk=unidade_id).first()

    contagem = contagem_por_situacao(
        tenant=request.tenant,
        unidade=unidade_filtro,
    )

    # Agrupa em memoria: uma query so, e o volume de uma rede cabe folgado.
    # Vira paginacao por coluna quando alguma passar de algumas centenas.
    por_situacao = {situacao: [] for situacao in estados.COLUNAS_BOARD}
    for colaborador in colaboradores:
        if colaborador.situacao in por_situacao:
            por_situacao[colaborador.situacao].append(colaborador)

    colunas = [
        {
            'situacao': situacao,
            'rotulo': estados.rotulo(situacao),
            'total': contagem.get(situacao, 0),
            'cards': por_situacao[situacao],
        }
        for situacao in estados.COLUNAS_BOARD
    ]

    contexto = {
        'pagetitle': 'Board',
        'colunas': colunas,
        'unidades_opcoes': list(
            Unidade.objects.filter(ativo=True).values_list('pk', 'nome')),
        'unidade_selecionada': unidade_id,
        'pontos_entrada': estados.PONTOS_ENTRADA_CHOICES,
        'pode_mover': pode_acessar(request, 'people.mover_colaborador'),
        'pode_criar': pode_acessar(request, 'people.criar_colaborador'),
    }
    return render(request, 'people/board.html', contexto)


@require_POST
@requer_people('people.mover_colaborador', json=True)
def api_mover(request, pk):
    """
    Move o colaborador de fase. Nao contem regra: chama o servico e traduz o
    que ele responde.
    """
    colaborador = get_object_or_404(Colaborador.objects, pk=pk)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Payload invalido.'}, status=400)

    situacao = payload.get('situacao')
    dados = payload.get('dados') or {}

    try:
        atualizado = mover_situacao(
            colaborador, situacao,
            motivo=payload.get('motivo', ''),
            usuario=request.user, request=request,
            origem='painel', dados=dados,
        )
    except TransicaoInvalida as erro:
        return JsonResponse({'erro': str(erro)}, status=400)
    except CampoObrigatorioFaltando as erro:
        return JsonResponse({
            'erro': 'Preencha antes de mover',
            'campos_faltando': [
                {
                    'nome': campo,
                    'label': CAMPOS_DA_TRANSICAO.get(campo, {}).get('label', campo),
                    'tipo': CAMPOS_DA_TRANSICAO.get(campo, {}).get('tipo', 'text'),
                }
                for campo in erro.campos
            ],
        }, status=400)

    return JsonResponse({
        'ok': True,
        'situacao': atualizado.situacao,
        'rotulo': f'{atualizado.nome_completo} agora esta em {atualizado.situacao_rotulo}.',
        'destinos': estados.destinos_possiveis(atualizado.situacao),
    })
