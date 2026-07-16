"""
Central de Acoes — coletor dos sinais de "o que fazer agora", escopado por
papel via escopo_responsaveis (vendedor ve o dele, gerente ve o do time).

Cada sinal vira um item {tipo, titulo, subtitulo, tag, url, ordem}, agrupado
por severidade (critico / atencao / oportunidade). O `tipo` e o selo que diz
O QUE e cada linha (Parada, Sem dono, Tarefa, Erro, Nova).

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

# Teto por sinal, pra nao explodir a pagina numa base grande.
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
    """Devolve {grupos, contadores, ve_time}. grupos = 3 baldes por severidade,
    cada item ja rotulado (tipo) e ordenado por urgencia. Tudo escopado."""
    from apps.comercial.crm.models import OportunidadeVenda, TarefaCRM
    from apps.comercial.leads.models import LeadProspecto

    esc = escopo_responsaveis(request)          # None = ve tudo; senao lista de ids
    ve_time = esc is None or len(esc) > 1        # heuristica: gestor/admin (ve alem de si)
    agora = timezone.now()

    criticos, atencao, oportunidades = [], [], []

    def add(bucket, tipo, titulo, subtitulo, tag, url, ordem):
        bucket.append({'tipo': tipo, 'titulo': titulo, 'subtitulo': subtitulo,
                       'tag': tag, 'url': url, 'ordem': ordem})

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
        nome = op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}'
        sub = f'{dias} dia{_plural(dias)} parada em {op.estagio.nome}'
        add(criticos if dias > 7 else atencao, 'Parada', nome, sub, _equipe_nome(op), _url_op(op), dias)

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
        add(criticos, 'Tarefa', nome, f'Vencida ha {dias} dia{_plural(dias)}: {t.titulo}',
            '', _url_op(alvo), dias + 5)

    # 4. Oportunidade sem dono — so pra quem ve o time (gestor/admin)
    if ve_time:
        orfas = op_base.filter(responsavel__isnull=True).order_by('data_criacao')
        for op in orfas[:LIMITE_POR_SINAL]:
            dias = (agora - op.data_criacao).days
            nome = op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}'
            add(criticos, 'Sem dono', nome, f'{dias} dia{_plural(dias)} sem responsavel, precisa atribuir',
                op.estagio.nome, _url_op(op), dias + 100)

    # 5. Lead em status de erro (falha de sincronizacao)
    erros = LeadProspecto.objects.filter(status_api='erro').select_related('oportunidade_crm')
    if esc is not None:
        erros = erros.filter(oportunidade_crm__responsavel_id__in=esc)
    for l in erros.order_by('-data_cadastro')[:LIMITE_POR_SINAL]:
        op = getattr(l, 'oportunidade_crm', None)
        nome = l.nome_razaosocial or f'Lead #{l.pk}'
        add(criticos, 'Erro', nome, 'Falha de sincronizacao com o ERP', '', _url_op(op), 9999)

    # 6. Oportunidade nova < 24h — primeiro contato agora
    novas = (escopar_op(op_base)
             .filter(data_criacao__gte=agora - timedelta(hours=24))
             .order_by('-data_criacao'))
    for op in novas[:LIMITE_POR_SINAL]:
        horas = int((agora - op.data_criacao).total_seconds() // 3600)
        nome = op.lead.nome_razaosocial or op.titulo or f'Oportunidade #{op.pk}'
        add(oportunidades, 'Nova', nome, f'Nova ha {horas}h, faca o primeiro contato',
            _equipe_nome(op), _url_op(op), -horas)

    criticos.sort(key=lambda i: -i['ordem'])
    atencao.sort(key=lambda i: -i['ordem'])
    oportunidades.sort(key=lambda i: -i['ordem'])

    grupos = [
        {'sev': 'critico', 'label': 'Críticos', 'itens': criticos},
        {'sev': 'atencao', 'label': 'Atenção', 'itens': atencao},
        {'sev': 'oportunidade', 'label': 'Oportunidades', 'itens': oportunidades},
    ]
    contadores = {'criticos': len(criticos), 'atencao': len(atencao),
                  'oportunidades': len(oportunidades)}
    return {'grupos': grupos, 'contadores': contadores, 've_time': ve_time}
