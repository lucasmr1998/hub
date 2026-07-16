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

from django.db.models import Count, DateTimeField, ExpressionWrapper, F, Q, Sum
from django.urls import reverse
from django.utils import timezone

from apps.comercial.crm.escopo import escopo_responsaveis

# Prazo do SLA de cada op: entrada no estagio + sla_horas do estagio. Op parada =
# esse prazo ja passou. Estagio sem sla_horas nao gera parada (sla_vencido=False).
_SLA_DEADLINE = ExpressionWrapper(
    F('data_entrada_estagio') + timedelta(hours=1) * F('estagio__sla_horas'),
    output_field=DateTimeField(),
)


def _tempo_no_estagio(horas):
    """Formata o tempo no estagio: '5h' ou '3 dias'."""
    if horas < 24:
        return f'{int(horas)}h'
    d = int(horas // 24)
    return f'{d} dia{"s" if d != 1 else ""}'


def pode_ver_time(request):
    """True pra gestor/supervisor/admin (ve alem de si). Sempre pelo escopo BASE
    (permissao), independente do filtro aplicado."""
    base = escopo_responsaveis(request)
    return base is None or len(base) > 1


def escopo_efetivo(request):
    """Escopo base (permissao) estreitado pelos filtros server-side ?pessoa e
    ?equipe. Pessoa tem prioridade sobre equipe. Devolve None (tudo) ou lista."""
    base = escopo_responsaveis(request)
    pessoa = (request.GET.get('pessoa') or '').strip()
    equipe = (request.GET.get('equipe') or '').strip()
    if pessoa.isdigit():
        pid = int(pessoa)
        if base is None or pid in base:
            return [pid]
    if equipe.isdigit():
        from apps.comercial.crm.models import PerfilVendedor
        membros = set(PerfilVendedor.objects.filter(equipe_id=int(equipe), ativo=True)
                      .values_list('user_id', flat=True))
        if base is not None:
            membros &= set(base)
        return sorted(membros)
    return base


def opcoes_filtro(request):
    """Opcoes dos dropdowns de equipe e pessoa (so pra quem ve o time) + o que
    esta selecionado. Equipes = os times visiveis; pessoas = o escopo base."""
    from django.contrib.auth.models import User
    from apps.comercial.crm.models import EquipeVendas, PerfilVendedor
    from apps.comercial.crm.escopo import times_visiveis

    base = escopo_responsaveis(request)
    if base is None:
        eq_qs = EquipeVendas.objects.filter(ativo=True)
        pids = list(PerfilVendedor.objects.filter(ativo=True).values_list('user_id', flat=True))
    else:
        eq_qs = EquipeVendas.objects.filter(id__in=times_visiveis(request.user), ativo=True)
        pids = list(base)
    equipes = [(e.id, e.nome) for e in eq_qs.order_by('nome')]
    pessoas = [(u.id, (u.get_full_name() or u.username).strip())
               for u in User.objects.filter(id__in=pids).order_by('first_name', 'username')]
    return {
        'equipes': equipes, 'pessoas': pessoas,
        'sel_equipe': (request.GET.get('equipe') or '').strip(),
        'sel_pessoa': (request.GET.get('pessoa') or '').strip(),
        'mostrar': base is None or len(base) > 1,
    }

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


def _equipe_de(user):
    """Nome da equipe do usuario (via PerfilVendedor), '' se nao tiver."""
    perfil = getattr(user, 'perfil_crm', None) if user else None
    eq = getattr(perfil, 'equipe', None) if perfil else None
    return eq.nome if eq else ''


def _equipe_nome(op):
    return _equipe_de(getattr(op, 'responsavel', None)) if op else ''


def _plural(n):
    return 's' if n != 1 else ''


def coletar_acoes(request):
    """Devolve {itens, tipos, equipes, contadores, ve_time}."""
    from apps.comercial.crm.models import OportunidadeVenda, TarefaCRM
    from apps.comercial.leads.models import LeadProspecto

    esc = escopo_efetivo(request)               # base estreitado pelos filtros
    ve_time = pode_ver_time(request)            # gate pelo escopo base (permissao)
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

    # Parada = passou do SLA do estagio (data_entrada_estagio + sla_horas < agora).
    # Estagio sem SLA nao gera parada. Severidade: critico se passou 2x o SLA.
    paradas = (escopar_op(op_base)
               .filter(estagio__sla_horas__isnull=False)
               .annotate(_sla_dl=_SLA_DEADLINE)
               .filter(_sla_dl__lt=agora)
               .order_by('data_entrada_estagio'))
    for op in paradas[:LIMITE_POR_SINAL]:
        horas = (agora - op.data_entrada_estagio).total_seconds() / 3600
        sla = op.estagio.sla_horas or 0
        sev = 'critico' if sla and horas > 2 * sla else 'atencao'
        nome = op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}'
        add('parada', 'Parada', sev, nome,
            f'{_tempo_no_estagio(horas)} parada em {op.estagio.nome}',
            _equipe_nome(op), _url_op(op), int(horas - sla))

    # Tarefa vencida
    tarefas = (TarefaCRM.objects.filter(data_vencimento__lt=agora,
                                        status__in=['pendente', 'em_andamento'])
               .select_related('lead', 'oportunidade', 'oportunidade__lead',
                               'responsavel__perfil_crm__equipe'))
    if esc is not None:
        tarefas = tarefas.filter(responsavel_id__in=esc)
    for t in tarefas.order_by('data_vencimento')[:LIMITE_POR_SINAL]:
        dias = (agora - t.data_vencimento).days
        alvo = t.oportunidade
        nome = (alvo.lead.nome_razaosocial if alvo and alvo.lead else None) or t.titulo
        add('tarefa', 'Tarefa', 'critico', nome,
            f'Vencida ha {dias} dia{_plural(dias)}: {t.titulo}', _equipe_de(t.responsavel), _url_op(alvo), dias + 5)

    # Lead em erro
    erros = LeadProspecto.objects.filter(status_api='erro').select_related(
        'oportunidade_crm', 'oportunidade_crm__responsavel__perfil_crm__equipe')
    if esc is not None:
        erros = erros.filter(oportunidade_crm__responsavel_id__in=esc)
    for l in erros.order_by('-data_cadastro')[:LIMITE_POR_SINAL]:
        op = getattr(l, 'oportunidade_crm', None)
        nome = l.nome_razaosocial or f'Lead #{l.pk}'
        add('erro', 'Erro', 'critico', nome, 'Falha de sincronizacao com o ERP', _equipe_nome(op), _url_op(op), 9999)

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
    contadores = {
        'criticos': sum(1 for i in itens if i['severidade'] == 'critico'),
        'atencao': sum(1 for i in itens if i['severidade'] == 'atencao'),
        'oportunidades': sum(1 for i in itens if i['severidade'] == 'oportunidade'),
    }
    return {'itens': itens, 'colunas': colunas,
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

    esc = escopo_efetivo(request)
    ve_time = pode_ver_time(request)
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


def tabela_operacional(request):
    """Tabela operacional por vendedor (uma linha por membro do escopo), com
    colunas agrupadas em Oportunidades e Tarefas. So pra quem ve o time
    (gestor/supervisor). None pro vendedor comum. Numeros do mes corrente pros
    fluxos; estado atual pro resto. Cada celula linka pra a lista do vendedor."""
    from django.contrib.auth.models import User
    from apps.comercial.crm.models import OportunidadeVenda, TarefaCRM, PerfilVendedor

    ve_time = pode_ver_time(request)
    if not ve_time:
        return None
    esc = escopo_efetivo(request)

    agora = timezone.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    aberto_q = Q(ativo=True) & ~Q(estagio__is_final_ganho=True) & ~Q(estagio__is_final_perdido=True)
    aberta = ['pendente', 'em_andamento']

    if esc is None:
        user_ids = list(PerfilVendedor.objects.filter(ativo=True).values_list('user_id', flat=True))
    else:
        user_ids = list(esc)
    if not user_ids:
        return {'linhas': [], 'total': None}

    ops = {r['responsavel_id']: r for r in (
        OportunidadeVenda.objects.filter(responsavel_id__in=user_ids)
        .values('responsavel_id').annotate(
            criadas=Count('id', filter=Q(data_criacao__gte=inicio_mes)),
            ganhas=Count('id', filter=Q(estagio__is_final_ganho=True, data_atualizacao__gte=inicio_mes)),
            perdidas=Count('id', filter=Q(estagio__is_final_perdido=True, data_atualizacao__gte=inicio_mes)),
            aberto=Count('id', filter=aberto_q),
        ))}
    # Paradas por SLA (query a parte por causa da comparacao com o prazo do SLA).
    paradas_map = dict(
        OportunidadeVenda.objects
        .filter(responsavel_id__in=user_ids, estagio__sla_horas__isnull=False)
        .filter(aberto_q).annotate(_sla_dl=_SLA_DEADLINE).filter(_sla_dl__lt=agora)
        .values('responsavel_id').annotate(n=Count('id')).values_list('responsavel_id', 'n'))
    tars = {r['responsavel_id']: r for r in (
        TarefaCRM.objects.filter(responsavel_id__in=user_ids)
        .values('responsavel_id').annotate(
            feitas=Count('id', filter=Q(status='concluida', data_conclusao__gte=inicio_mes)),
            vencidas=Count('id', filter=Q(status__in=aberta, data_vencimento__lt=agora)),
            pendentes=Count('id', filter=Q(status__in=aberta) & (
                Q(data_vencimento__gte=agora) | Q(data_vencimento__isnull=True))),
        ))}

    users = {u.id: u for u in User.objects.filter(id__in=user_ids).select_related('perfil_crm__equipe')}
    try:
        url_op = reverse('crm:oportunidades_lista')
    except Exception:
        url_op = '/crm/oportunidades/'
    try:
        url_tar = reverse('crm:tarefas_lista')
    except Exception:
        url_tar = '/crm/tarefas/'

    campos = ('criadas', 'ganhas', 'perdidas', 'aberto', 'paradas', 'feitas', 'pendentes', 'vencidas')
    linhas = []
    for uid in user_ids:
        u = users.get(uid)
        if not u:
            continue
        o, t = ops.get(uid, {}), tars.get(uid, {})
        nome = (u.get_full_name() or u.username).strip()
        linhas.append({
            'nome': nome, 'inicial': (nome[:1] or '?').upper(),
            'equipe': _equipe_de(u),
            'criadas': o.get('criadas', 0), 'ganhas': o.get('ganhas', 0),
            'perdidas': o.get('perdidas', 0), 'aberto': o.get('aberto', 0),
            'paradas': paradas_map.get(uid, 0), 'feitas': t.get('feitas', 0),
            'pendentes': t.get('pendentes', 0), 'vencidas': t.get('vencidas', 0),
            'url_op': f'{url_op}?responsavel={uid}',
            'url_tar': f'{url_tar}?responsavel={uid}',
        })
    linhas.sort(key=lambda r: (-r['ganhas'], -r['aberto']))
    total = {c: sum(r[c] for r in linhas) for c in campos}
    return {'linhas': linhas, 'total': total}
