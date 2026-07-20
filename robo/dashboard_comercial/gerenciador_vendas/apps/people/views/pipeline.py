"""
Board do pipeline de recrutamento.

Uma coluna por etapa configurada, card por candidato, arrasto pra mover. E irmao
do board do DP, com duas diferencas que vem do dominio:

1. As colunas sao DADO (EtapaPipeline), nao literais fixos. O tenant configurou.
2. Mover entre etapas e livre; sair do pipeline exige motivo e passa pela regra
   de saida. Por isso a saida nao e arrasto, e acao com modal.

A view nao contem regra: chama os servicos de pipeline e traduz o que voltam.
"""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.people import estados_recrutamento as estados_rs
from apps.people.excecoes import CampoObrigatorioFaltando, TransicaoInvalida
from apps.people.models import Candidato, EtapaPipeline, Unidade, Vaga
from apps.people.permissoes import pode_acessar, requer_people
from apps.people.services.pipeline import dar_saida, mover_para_etapa, reabrir


@requer_people()
def board(request):
    unidade_id = (request.GET.get('unidade') or '').strip()
    vaga_id = (request.GET.get('vaga') or '').strip()

    unidade = None
    if unidade_id.isdigit():
        unidade = Unidade.objects.filter(pk=unidade_id).first()

    etapas = list(EtapaPipeline.do_escopo(request.tenant, unidade)
                  .order_by('ordem', 'id'))

    candidatos = (Candidato.objects
                  .select_related('vaga', 'vaga__cargo', 'unidade', 'etapa',
                                  'link_origem')
                  .filter(saida='', anonimizado_em__isnull=True))
    if unidade is not None:
        candidatos = candidatos.filter(unidade=unidade)
    if vaga_id.isdigit():
        candidatos = candidatos.filter(vaga_id=int(vaga_id))

    # Agrupa em memoria: uma query so, volume de uma rede cabe folgado.
    por_etapa = {etapa.pk: [] for etapa in etapas}
    sem_etapa = []  # candidato numa etapa desativada, ou sem etapa nenhuma
    ids_visiveis = set(por_etapa)
    for candidato in candidatos.order_by('-criado_em'):
        if candidato.etapa_id in ids_visiveis:
            por_etapa[candidato.etapa_id].append(candidato)
        else:
            sem_etapa.append(candidato)

    colunas = [
        {'etapa': etapa, 'cards': por_etapa[etapa.pk],
         'total': len(por_etapa[etapa.pk])}
        for etapa in etapas
    ]

    return render(request, 'people/pipeline_board.html', {
        'pagetitle': 'Candidatos',
        'colunas': colunas,
        'sem_etapa': sem_etapa,
        'saidas': [{'valor': v, 'rotulo': r} for v, r in estados_rs.SAIDAS],
        'unidades_opcoes': list(
            Unidade.objects.filter(ativo=True).values_list('pk', 'nome')),
        'unidade_selecionada': unidade_id,
        'vagas_opcoes': list(
            Vaga.objects.exclude(status='encerrada')
            .values_list('pk', 'titulo')),
        'vaga_selecionada': vaga_id,
        'pode_mover': pode_acessar(request, 'people.gerir_vagas'),
        'tem_etapas': bool(etapas),
    })


@require_POST
@requer_people('people.gerir_vagas', json=True)
def api_mover(request, pk):
    """Move o candidato pra uma etapa. Sem regra: delega e traduz."""
    candidato = get_object_or_404(
        Candidato.objects.select_related('etapa', 'colaborador'), pk=pk)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Payload invalido.'}, status=400)

    etapa = get_object_or_404(EtapaPipeline.objects,
                              pk=payload.get('etapa_id'))

    # Vinha de uma saida terminal? Entao e reabertura, e a regra e outra.
    if candidato.saida:
        try:
            reabrir(candidato, etapa, usuario=request.user)
        except TransicaoInvalida as erro:
            return JsonResponse({'erro': str(erro)}, status=400)
    else:
        mover_para_etapa(candidato, etapa, usuario=request.user)

    return JsonResponse({'ok': True, 'etapa_id': etapa.pk})


@require_POST
@requer_people('people.gerir_vagas', json=True)
def api_dar_saida(request, pk):
    """
    Tira o candidato do pipeline por uma saida terminal.

    Devolve 400 com `precisa_motivo` quando falta motivo, pra interface pedir
    em vez de recusar calada, no mesmo padrao do board do DP.
    """
    candidato = get_object_or_404(
        Candidato.objects.select_related('colaborador'), pk=pk)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Payload invalido.'}, status=400)

    saida = payload.get('saida', '')
    motivo = (payload.get('motivo') or '').strip()

    try:
        dar_saida(candidato, saida, motivo=motivo, usuario=request.user)
    except CampoObrigatorioFaltando:
        return JsonResponse({
            'erro': 'Registre o motivo antes de tirar do processo.',
            'precisa_motivo': True,
        }, status=400)
    except TransicaoInvalida as erro:
        return JsonResponse({'erro': str(erro)}, status=400)

    # Regra de parada (4.4): admitir alem do limite e permitido, porem sinalizado.
    # A decisao e do RH; o sistema so garante que passar do teto seja consciente.
    aviso = ''
    if (saida == estados_rs.SAIDA_ADMITIDO and candidato.vaga_id
            and candidato.vaga.atingiu_limite):
        aviso = (f'Esta vaga já atingiu o limite de {candidato.vaga.limite_aprovados} '
                 f'aprovados. Considere encerrar a vaga.')

    return JsonResponse({'ok': True, 'saida': saida,
                         'rotulo': estados_rs.rotulo_saida(saida),
                         'aviso': aviso})
