"""
Central de Acoes — coletor dos sinais de "o que fazer agora", escopado por
papel via escopo_responsaveis (vendedor ve o dele, gerente ve o do time).

Cada sinal vira um item {severidade, titulo, subtitulo, tag, url, ordem}.
Severidades: 'critico' (vermelho), 'atencao' (amarelo), 'oportunidade' (verde).

MVP com 6 sinais (regua do strawman aprovado):
  - Oportunidade parada no estagio > 7d (critico) / 3-7d (atencao)
  - Tarefa vencida (critico)
  - Oportunidade sem dono (critico) — so pra quem ve o time
  - Lead em status de erro (critico)
  - Oportunidade nova < 24h (oportunidade)
"""
from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.comercial.crm.escopo import escopo_responsaveis

# Teto por sinal, pra nao explodir a pagina numa base grande. Os contadores
# refletem o que foi coletado (ate este teto).
LIMITE_POR_SINAL = 150


def _url_op(op):
    if not op:
        return '#'
    try:
        return reverse('crm:oportunidade_detalhe', args=[op.pk])
    except Exception:
        return '#'


def _equipe_nome(op):
    resp = getattr(op, 'responsavel', None)
    perfil = getattr(resp, 'perfil_crm', None) if resp else None
    eq = getattr(perfil, 'equipe', None) if perfil else None
    return eq.nome if eq else ''


def _plural(n):
    return 's' if n != 1 else ''


def coletar_acoes(request):
    """Devolve {itens, contadores, ve_time}. itens ja ordenado por severidade e
    urgencia. Tudo filtrado pelo escopo do usuario."""
    from apps.comercial.crm.models import OportunidadeVenda, TarefaCRM
    from apps.comercial.leads.models import LeadProspecto

    esc = escopo_responsaveis(request)          # None = ve tudo; senao lista de ids
    ve_time = esc is None or len(esc) > 1        # heuristica: gestor/admin (ve alem de si)
    agora = timezone.now()
    itens = []

    op_base = (OportunidadeVenda.objects.filter(ativo=True)
               .exclude(Q(estagio__is_final_ganho=True) | Q(estagio__is_final_perdido=True))
               .select_related('lead', 'estagio', 'responsavel', 'responsavel__perfil_crm__equipe'))

    def escopar_op(qs):
        return qs if esc is None else qs.filter(responsavel_id__in=esc)

    # 1 + 2. Oportunidade parada no estagio (>7d critico, 3-7d atencao)
    paradas = (escopar_op(op_base)
               .filter(data_entrada_estagio__lt=agora - timedelta(days=3))
               .order_by('data_entrada_estagio'))
    for op in paradas[:LIMITE_POR_SINAL]:
        dias = (agora - op.data_entrada_estagio).days
        itens.append({
            'severidade': 'critico' if dias > 7 else 'atencao',
            'titulo': op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}',
            'subtitulo': f'{dias} dia{_plural(dias)} sem acao em {op.estagio.nome}',
            'tag': _equipe_nome(op),
            'url': _url_op(op),
            'ordem': dias,
        })

    # 3. Tarefa vencida
    tarefas = (TarefaCRM.objects.filter(data_vencimento__lt=agora,
                                        status__in=['pendente', 'em_andamento'])
               .select_related('lead', 'oportunidade', 'oportunidade__lead', 'responsavel'))
    if esc is not None:
        tarefas = tarefas.filter(responsavel_id__in=esc)
    for t in tarefas.order_by('data_vencimento')[:LIMITE_POR_SINAL]:
        dias = (agora - t.data_vencimento).days
        alvo = t.oportunidade
        nome = (alvo.lead.nome_razaosocial if alvo and alvo.lead else None) or t.titulo
        itens.append({
            'severidade': 'critico',
            'titulo': nome,
            'subtitulo': f'Tarefa vencida ha {dias} dia{_plural(dias)}: {t.titulo}',
            'tag': '',
            'url': _url_op(alvo),
            'ordem': dias + 5,  # vencida pesa um pouco mais que parada
        })

    # 4. Oportunidade sem dono — so pra quem ve o time (gestor/admin)
    if ve_time:
        orfas = op_base.filter(responsavel__isnull=True).order_by('data_criacao')
        for op in orfas[:LIMITE_POR_SINAL]:
            dias = (agora - op.data_criacao).days
            itens.append({
                'severidade': 'critico',
                'titulo': op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}',
                'subtitulo': f'Sem responsavel ha {dias} dia{_plural(dias)}, precisa atribuir',
                'tag': 'sem dono',
                'url': _url_op(op),
                'ordem': dias + 10,
            })

    # 5. Lead em status de erro (falha de sincronizacao)
    erros = LeadProspecto.objects.filter(status_api='erro').select_related('oportunidade_crm')
    if esc is not None:
        erros = erros.filter(oportunidade_crm__responsavel_id__in=esc)
    for l in erros.order_by('-data_cadastro')[:LIMITE_POR_SINAL]:
        op = getattr(l, 'oportunidade_crm', None)
        itens.append({
            'severidade': 'critico',
            'titulo': l.nome_razaosocial or f'Lead #{l.pk}',
            'subtitulo': 'Lead em erro (falha de sincronizacao com o ERP)',
            'tag': '',
            'url': _url_op(op),
            'ordem': 999,  # erro tecnico no topo dos criticos
        })

    # 6. Oportunidade nova < 24h — primeiro contato agora
    novas = (escopar_op(op_base)
             .filter(data_criacao__gte=agora - timedelta(hours=24))
             .order_by('-data_criacao'))
    for op in novas[:LIMITE_POR_SINAL]:
        horas = int((agora - op.data_criacao).total_seconds() // 3600)
        itens.append({
            'severidade': 'oportunidade',
            'titulo': op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}',
            'subtitulo': f'Nova ha {horas}h, faca o primeiro contato',
            'tag': _equipe_nome(op),
            'url': _url_op(op),
            'ordem': -horas,  # mais nova primeiro dentro do verde
        })

    peso = {'critico': 0, 'atencao': 1, 'oportunidade': 2}
    itens.sort(key=lambda i: (peso[i['severidade']], -i['ordem']))

    contadores = {
        'criticos': sum(1 for i in itens if i['severidade'] == 'critico'),
        'atencao': sum(1 for i in itens if i['severidade'] == 'atencao'),
        'oportunidades': sum(1 for i in itens if i['severidade'] == 'oportunidade'),
    }
    return {'itens': itens, 'contadores': contadores, 've_time': ve_time}
