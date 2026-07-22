"""
Board do pipeline de recrutamento.

A tela e uma barra de chips (uma etapa por chip, com contador) mais a LISTA da
selecao, e nao colunas simultaneas. A diferenca nao e estetica: a operacao real
do produto de origem mostra 76 candidatos numa unica etapa, e coluna lado a lado
nao aguenta esse volume. O kanban continua disponivel por toggle, porque com
poucos candidatos ele e melhor pra mover.

As SAIDAS tambem sao chips. Antes o board filtrava `saida=''` e quem saia do
pipeline sumia da interface: o candidato ficava no banco e nao havia tela que
chegasse nele, apesar de o banco de talentos ser descrito pela spec como sendo o
produto.

A view nao contem regra: chama os servicos de pipeline e traduz o que voltam.
"""
import json

from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.people import estados_recrutamento as estados_rs
from apps.people.excecoes import CampoObrigatorioFaltando, TransicaoInvalida
from apps.people.models import Candidato, EtapaPipeline, Unidade, Vaga
from apps.people.models_recrutamento import CANAL_CHOICES
from apps.people.permissoes import pode_acessar, requer_people
from apps.people.services.pipeline import dar_saida, mover_para_etapa, reabrir


# Chave da selecao "quem esta numa etapa que foi desativada". Nao e uma etapa
# real, e um agrupamento pra que esses candidatos nao fiquem invisiveis.
SEM_ETAPA = 'sem-etapa'


def _candidatos_visiveis(request, unidade, vaga_id):
    """Base de candidatos da tela, ja com os filtros do topo aplicados."""
    base = (Candidato.objects
            .select_related('vaga', 'vaga__cargo', 'unidade', 'etapa',
                            'link_origem')
            .filter(anonimizado_em__isnull=True))
    if unidade is not None:
        base = base.filter(unidade=unidade)
    if vaga_id.isdigit():
        base = base.filter(vaga_id=int(vaga_id))

    busca = (request.GET.get('busca') or '').strip()
    if busca:
        base = base.filter(nome_completo__icontains=busca)

    # Canal e periodo: os filtros que o board da origem tem e o nosso nao
    # tinha. Canal responde "que canal esta trazendo gente"; periodo separa a
    # safra desta semana do acumulado, que num board com 400 candidatos e a
    # diferenca entre a tela servir e nao servir.
    canal = (request.GET.get('canal') or '').strip()
    if canal:
        base = base.filter(link_origem__canal=canal)

    dias = (request.GET.get('periodo') or '').strip()
    if dias.isdigit():
        from datetime import timedelta

        from django.utils import timezone
        base = base.filter(
            criado_em__gte=timezone.now() - timedelta(days=int(dias)))
    return base


@requer_people()
def board(request):
    unidade_id = (request.GET.get('unidade') or '').strip()
    vaga_id = (request.GET.get('vaga') or '').strip()
    busca = (request.GET.get('busca') or '').strip()

    unidade = None
    if unidade_id.isdigit():
        unidade = Unidade.objects.filter(pk=unidade_id).first()

    etapas = list(EtapaPipeline.do_escopo(request.tenant, unidade)
                  .order_by('ordem', 'id'))
    ids_etapas = {e.pk for e in etapas}

    base = _candidatos_visiveis(request, unidade, vaga_id)

    # Contagens numa consulta por eixo, nao uma por chip.
    por_etapa = dict(base.filter(saida='')
                     .values_list('etapa').annotate(n=Count('id')))
    por_saida = dict(base.exclude(saida='')
                     .values_list('saida').annotate(n=Count('id')))

    # Quem esta em etapa desativada (ou sem etapa) cai num chip proprio, em vez
    # de sumir. Some as chaves que nao sao de etapa ativa, inclusive None.
    fora_de_etapa = sum(n for pk, n in por_etapa.items() if pk not in ids_etapas)

    chips = [
        {'tipo': 'etapa', 'chave': str(e.pk), 'rotulo': e.nome,
         'cor': e.cor_hex, 'total': por_etapa.get(e.pk, 0)}
        for e in etapas
    ]
    if fora_de_etapa:
        chips.append({'tipo': 'etapa', 'chave': SEM_ETAPA,
                      'rotulo': 'Fora de etapa', 'cor': '#F59E0B',
                      'total': fora_de_etapa, 'alerta': True})

    chips_saida = [
        {'tipo': 'saida', 'chave': valor, 'rotulo': rotulo,
         'cor': estados_rs.COR_DA_SAIDA.get(valor, '#6B7280'),
         'total': por_saida.get(valor, 0)}
        for valor, rotulo in estados_rs.SAIDAS
    ]

    # ── Selecao ─────────────────────────────────────────────────────────────
    saida_sel = (request.GET.get('saida') or '').strip()
    etapa_sel = (request.GET.get('etapa') or '').strip()

    if saida_sel in estados_rs.VALORES_SAIDA:
        lista = base.filter(saida=saida_sel)
        selecao = {'tipo': 'saida', 'chave': saida_sel,
                   'rotulo': estados_rs.rotulo_saida(saida_sel)}
    elif etapa_sel == SEM_ETAPA:
        lista = base.filter(saida='').exclude(etapa_id__in=ids_etapas)
        selecao = {'tipo': 'etapa', 'chave': SEM_ETAPA,
                   'rotulo': 'Fora de etapa'}
    elif etapa_sel.isdigit() and int(etapa_sel) in ids_etapas:
        lista = base.filter(saida='', etapa_id=int(etapa_sel))
        alvo = next(e for e in etapas if e.pk == int(etapa_sel))
        selecao = {'tipo': 'etapa', 'chave': etapa_sel, 'rotulo': alvo.nome}
    elif etapas:
        # Default: a primeira etapa do fluxo.
        primeira = etapas[0]
        lista = base.filter(saida='', etapa_id=primeira.pk)
        selecao = {'tipo': 'etapa', 'chave': str(primeira.pk),
                   'rotulo': primeira.nome}
    else:
        lista = base.none()
        selecao = {'tipo': 'etapa', 'chave': '', 'rotulo': ''}

    for chip in chips + chips_saida:
        chip['ativo'] = (chip['tipo'] == selecao['tipo']
                         and chip['chave'] == selecao['chave'])

    # ── Vista kanban (opcional) ─────────────────────────────────────────────
    vista = 'kanban' if request.GET.get('vista') == 'kanban' else 'lista'
    colunas = []
    if vista == 'kanban':
        por_etapa_cards = {e.pk: [] for e in etapas}
        soltos = []
        for candidato in base.filter(saida='').order_by('-criado_em'):
            if candidato.etapa_id in por_etapa_cards:
                por_etapa_cards[candidato.etapa_id].append(candidato)
            else:
                soltos.append(candidato)
        colunas = [
            {'etapa': e, 'cards': por_etapa_cards[e.pk],
             'total': len(por_etapa_cards[e.pk])}
            for e in etapas
        ]

    return render(request, 'people/pipeline_board.html', {
        'pagetitle': 'Candidatos',
        'chips': chips,
        'chips_saida': chips_saida,
        'selecao': selecao,
        'lista': lista.order_by('-criado_em'),
        'colunas': colunas,
        'vista': vista,
        'etapas': etapas,
        'saidas': [{'valor': v, 'rotulo': r} for v, r in estados_rs.SAIDAS],
        'unidades_opcoes': list(
            Unidade.objects.filter(ativo=True).values_list('pk', 'nome')),
        'canais_opcoes': CANAL_CHOICES,
        'canal_selecionado': (request.GET.get('canal') or '').strip(),
        'periodos_opcoes': [('7', 'Últimos 7 dias'), ('30', 'Últimos 30 dias'),
                            ('90', 'Últimos 90 dias')],
        'periodo_selecionado': (request.GET.get('periodo') or '').strip(),
        'motivos_saida': estados_rs.MOTIVOS_SAIDA,
        'unidade_selecionada': unidade_id,
        'vagas_opcoes': list(
            Vaga.objects.exclude(status='encerrada').values_list('pk', 'titulo')),
        'vaga_selecionada': vaga_id,
        'busca': busca,
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

    etapa = get_object_or_404(EtapaPipeline.objects, pk=payload.get('etapa_id'))

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
    motivo_codigo = (payload.get('motivo_codigo') or '').strip()

    try:
        dar_saida(candidato, saida, motivo=motivo,
                  motivo_codigo=motivo_codigo, usuario=request.user)
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


@require_POST
@requer_people('people.gerir_vagas', json=True)
def api_lote(request):
    """
    Aplica a mesma acao a varios candidatos de uma vez.

    Existe por volume: com dezenas de candidatos numa etapa, mover um a um e o
    tipo de trabalho que faz o RH desistir da ferramenta e voltar pra planilha.

    Processa um a um pelos mesmos servicos, e nao por `queryset.update()`: cada
    movimento precisa gerar historico, e um update em massa passaria por cima
    disso deixando o funil cego.
    """
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Payload invalido.'}, status=400)

    ids = [i for i in (payload.get('ids') or []) if str(i).isdigit()]
    if not ids:
        return JsonResponse({'erro': 'Selecione ao menos um candidato.'}, status=400)

    acao = payload.get('acao')
    motivo = (payload.get('motivo') or '').strip()
    motivo_codigo = (payload.get('motivo_codigo') or '').strip()

    # Escopo de tenant no filtro: id vindo do cliente nao decide de quem e.
    candidatos = list(Candidato.objects.filter(pk__in=ids))

    movidos, recusados = 0, []

    if acao == 'etapa':
        etapa = get_object_or_404(EtapaPipeline.objects, pk=payload.get('etapa_id'))
        for candidato in candidatos:
            try:
                if candidato.saida:
                    reabrir(candidato, etapa, usuario=request.user)
                else:
                    mover_para_etapa(candidato, etapa, usuario=request.user)
                movidos += 1
            except TransicaoInvalida as erro:
                recusados.append(f'{candidato.nome_completo}: {erro}')

    elif acao == 'saida':
        saida = payload.get('saida', '')
        for candidato in candidatos:
            try:
                dar_saida(candidato, saida, motivo=motivo,
                  motivo_codigo=motivo_codigo, usuario=request.user)
                movidos += 1
            except CampoObrigatorioFaltando:
                return JsonResponse({
                    'erro': 'Registre o motivo antes de tirar do processo.',
                    'precisa_motivo': True,
                }, status=400)
            except TransicaoInvalida as erro:
                recusados.append(f'{candidato.nome_completo}: {erro}')
    else:
        return JsonResponse({'erro': 'Ação desconhecida.'}, status=400)

    return JsonResponse({'ok': True, 'movidos': movidos, 'recusados': recusados})
