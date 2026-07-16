"""
Central de Acoes — coletor dos sinais de "o que fazer agora", escopado por
papel via escopo_responsaveis (vendedor ve o dele, gerente ve o do time).

Layout Cockpit: cards por TIPO no topo (Parada / Sem dono / Tarefa / Erro /
Nova) + fila focada embaixo. Cada item carrega:
  {chave, tipo, severidade, titulo, subtitulo, tag, url, ordem}
- chave: slug do tipo (pro filtro dos cards)
- severidade: 'critico' | 'atencao' | 'oportunidade' (a bolinha da linha)

MVP com 6 sinais (regua do strawman aprovado):
  - Oportunidade parada no estagio > 7d (critico) / 3-7d (atencao)
  - Tarefa vencida (critico)
  - Oportunidade sem dono (critico) — so pra quem ve o time
  - Lead em status de erro (critico)
  - Oportunidade nova < 24h (oportunidade)
"""
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

from apps.comercial.crm.escopo import escopo_responsaveis

LIMITE_POR_SINAL = 150

# (chave, label singular, label da coluna, cor da coluna). A cor da LINHA vem
# da severidade real de cada item.
TIPOS_META = [
    ('parada', 'Parada', 'OP Paradas', 'atencao'),
    ('tarefa', 'Tarefa', 'Tarefas', 'critico'),
    ('erro', 'Erro', 'Erros', 'critico'),
    ('nova', 'Nova', 'Novas', 'oportunidade'),
]

_PESO_SEV = {'critico': 0, 'atencao': 1, 'oportunidade': 2}


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
    """Devolve {itens, tipos, equipes, contadores, ve_time}."""
    from apps.comercial.crm.models import OportunidadeVenda, TarefaCRM
    from apps.comercial.leads.models import LeadProspecto

    esc = escopo_responsaveis(request)          # None = ve tudo; senao lista de ids
    ve_time = esc is None or len(esc) > 1        # heuristica: gestor/admin
    agora = timezone.now()
    itens = []

    def add(chave, tipo, sev, titulo, subtitulo, tag, url, ordem):
        itens.append({'chave': chave, 'tipo': tipo, 'severidade': sev,
                      'titulo': titulo, 'subtitulo': subtitulo,
                      'tag': tag, 'url': url, 'ordem': ordem})

    op_base = (OportunidadeVenda.objects.filter(ativo=True)
               .exclude(Q(estagio__is_final_ganho=True) | Q(estagio__is_final_perdido=True))
               .select_related('lead', 'estagio', 'responsavel', 'responsavel__perfil_crm__equipe'))

    def escopar_op(qs):
        return qs if esc is None else qs.filter(responsavel_id__in=esc)

    # Parada no estagio (>7d critico, 3-7d atencao)
    paradas = (escopar_op(op_base)
               .filter(data_entrada_estagio__lt=agora - timedelta(days=3))
               .order_by('data_entrada_estagio'))
    for op in paradas[:LIMITE_POR_SINAL]:
        dias = (agora - op.data_entrada_estagio).days
        nome = op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}'
        add('parada', 'Parada', 'critico' if dias > 7 else 'atencao', nome,
            f'{dias} dia{_plural(dias)} parada em {op.estagio.nome}', _equipe_nome(op), _url_op(op), dias)

    # Tarefa vencida
    tarefas = (TarefaCRM.objects.filter(data_vencimento__lt=agora,
                                        status__in=['pendente', 'em_andamento'])
               .select_related('lead', 'oportunidade', 'oportunidade__lead', 'responsavel'))
    if esc is not None:
        tarefas = tarefas.filter(responsavel_id__in=esc)
    for t in tarefas.order_by('data_vencimento')[:LIMITE_POR_SINAL]:
        dias = (agora - t.data_vencimento).days
        alvo = t.oportunidade
        nome = (alvo.lead.nome_razaosocial if alvo and alvo.lead else None) or t.titulo
        add('tarefa', 'Tarefa', 'critico', nome,
            f'Vencida ha {dias} dia{_plural(dias)}: {t.titulo}', '', _url_op(alvo), dias + 5)

    # Lead em erro
    erros = LeadProspecto.objects.filter(status_api='erro').select_related('oportunidade_crm')
    if esc is not None:
        erros = erros.filter(oportunidade_crm__responsavel_id__in=esc)
    for l in erros.order_by('-data_cadastro')[:LIMITE_POR_SINAL]:
        op = getattr(l, 'oportunidade_crm', None)
        nome = l.nome_razaosocial or f'Lead #{l.pk}'
        add('erro', 'Erro', 'critico', nome, 'Falha de sincronizacao com o ERP', '', _url_op(op), 9999)

    # Oportunidade nova < 24h
    novas = (escopar_op(op_base)
             .filter(data_criacao__gte=agora - timedelta(hours=24))
             .order_by('-data_criacao'))
    for op in novas[:LIMITE_POR_SINAL]:
        horas = int((agora - op.data_criacao).total_seconds() // 3600)
        nome = op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}'
        add('nova', 'Nova', 'oportunidade', nome,
            f'Nova ha {horas}h, faca o primeiro contato', _equipe_nome(op), _url_op(op), -horas)

    itens.sort(key=lambda i: (_PESO_SEV[i['severidade']], -i['ordem']))

    por_tipo = {}
    for i in itens:
        por_tipo.setdefault(i['chave'], []).append(i)
    colunas = [{'chave': c, 'label': lp, 'sev': s, 'itens': por_tipo.get(c, []),
                'count': len(por_tipo.get(c, []))}
               for (c, ls, lp, s) in TIPOS_META]
    equipes = sorted({i['tag'] for i in itens if i['tag']})
    contadores = {
        'criticos': sum(1 for i in itens if i['severidade'] == 'critico'),
        'atencao': sum(1 for i in itens if i['severidade'] == 'atencao'),
        'oportunidades': sum(1 for i in itens if i['severidade'] == 'oportunidade'),
    }
    return {'itens': itens, 'colunas': colunas, 'equipes': equipes,
            'contadores': contadores, 've_time': ve_time}


def _fmt_rs(v):
    """R$ compacto: 82k, 1,2M."""
    v = float(v or 0)
    if v >= 1_000_000:
        return ('%.1fM' % (v / 1_000_000)).replace('.', ',')
    if v >= 1_000:
        return '%dk' % round(v / 1_000)
    return '%d' % v


def kpis_comerciais(request):
    """KPIs de estado/progresso do funil, escopados por papel (o mesmo numero
    vira 'meu' pro vendedor e 'do time' pro gestor). Separado das acoes: aqui e
    saude/progresso, la e o to-do."""
    from apps.comercial.crm.models import OportunidadeVenda

    esc = escopo_responsaveis(request)
    ve_time = esc is None or len(esc) > 1
    agora = timezone.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ha_7d = agora - timedelta(days=7)

    final = Q(estagio__is_final_ganho=True) | Q(estagio__is_final_perdido=True)

    def escopar(qs):
        return qs if esc is None else qs.filter(responsavel_id__in=esc)

    base = OportunidadeVenda.objects.com_valor_estimado()

    abertas = escopar(base.filter(ativo=True).exclude(final)).aggregate(
        n=Count('id'), v=Sum('valor_estimado_anotado'))
    ganhas = escopar(base.filter(estagio__is_final_ganho=True, data_atualizacao__gte=inicio_mes)).aggregate(
        n=Count('id'), v=Sum('valor_estimado_anotado'))
    perdidas_n = escopar(OportunidadeVenda.objects.filter(
        estagio__is_final_perdido=True, data_atualizacao__gte=inicio_mes)).count()
    novas_n = escopar(OportunidadeVenda.objects.filter(data_criacao__gte=ha_7d)).count()

    ganhas_n = ganhas['n'] or 0
    fechadas = ganhas_n + perdidas_n
    conversao = round(ganhas_n / fechadas * 100) if fechadas else 0

    try:
        url_pipe = reverse('crm:pipeline')
    except Exception:
        url_pipe = '/crm/'

    kpis = [
        {'label': 'Em negociação', 'valor': abertas['n'] or 0,
         'sub': 'R$ ' + _fmt_rs(abertas['v']), 'variant': 'info', 'icon': 'bi-briefcase', 'url': url_pipe},
        {'label': 'Ganhas no mês', 'valor': ganhas_n,
         'sub': 'R$ ' + _fmt_rs(ganhas['v']), 'variant': 'success', 'icon': 'bi-trophy', 'url': ''},
        {'label': 'Conversão (mês)', 'valor': f'{conversao}%',
         'sub': f'{ganhas_n} de {fechadas} fechadas', 'variant': 'primary', 'icon': 'bi-graph-up-arrow', 'url': ''},
        {'label': 'Novas (7 dias)', 'valor': novas_n,
         'sub': 'entrada de demanda', 'variant': 'primary', 'icon': 'bi-person-plus', 'url': ''},
    ]
    if ve_time:
        sem_dono_n = (OportunidadeVenda.objects.filter(ativo=True, responsavel__isnull=True)
                      .exclude(final).count())
        kpis.append({'label': 'Sem dono', 'valor': sem_dono_n, 'sub': 'a distribuir',
                     'variant': 'danger', 'icon': 'bi-person-dash', 'url': url_pipe + '?responsavel=sem'})
    return kpis
