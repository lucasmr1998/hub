"""Workspace home — visão executiva: projetos ativos, tarefas urgentes, docs recentes."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from apps.sistema.decorators import user_tem_funcionalidade
from apps.workspace.models import Documento, Projeto, Tarefa


@login_required
def home(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden('Sem permissão pra acessar Workspace.')

    hoje = timezone.now().date()
    em_7_dias = hoje + timezone.timedelta(days=7)

    projetos_ativos = Projeto.objects.filter(ativo=True, status__in=['planejamento', 'em_andamento']).order_by('-criado_em')[:8]
    tarefas_urgentes = Tarefa.objects.filter(
        status__in=['pendente', 'em_andamento'],
        data_limite__lte=em_7_dias,
    ).order_by('data_limite', 'prioridade')[:10]
    docs_recentes = Documento.objects.order_by('-atualizado_em')[:6]

    ctx = {
        'projetos_ativos': projetos_ativos,
        'tarefas_urgentes': tarefas_urgentes,
        'docs_recentes': docs_recentes,
        'total_projetos': Projeto.objects.filter(ativo=True).count(),
        'total_tarefas_pendentes': Tarefa.objects.filter(status__in=['pendente', 'em_andamento']).count(),
        'total_docs': Documento.objects.count(),
        'pagetitle': 'Workspace',
    }
    return render(request, 'workspace/home.html', ctx)


@login_required
def ceo(request):
    """Dashboard CEO: cockpit executivo cruzando workspace + negocio + agentes. Tenant-safe."""
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden('Sem permissão pra acessar Workspace.')
    tenant = getattr(request, 'tenant', None)
    ctx = {'pagetitle': 'Dashboard CEO'}
    if tenant is None:
        return render(request, 'workspace/ceo.html', ctx)

    from datetime import timedelta
    from django.db.models import Count, Sum
    from apps.workspace.models import Proposta, TAREFA_STATUS_CHOICES
    from apps.automacao.models import Agente
    from apps.comercial.crm.models import OportunidadeVenda, Venda
    from apps.comercial.leads.models import LeadProspecto
    from apps.integracoes.models import ClienteHubsoft
    from apps.suporte.models import Ticket

    d30 = timezone.now() - timezone.timedelta(days=30)

    # --- Negocio (mesmos models que as tools dos agentes consultam) ---
    pipeline = list(OportunidadeVenda.all_tenants.filter(tenant=tenant)
                    .values('estagio__nome').annotate(n=Count('id')).order_by('-n'))
    ctx['pipeline_total'] = sum(p['n'] for p in pipeline)
    ctx['pipeline_estagios'] = [{'nome': p['estagio__nome'] or 'sem estágio', 'n': p['n']} for p in pipeline[:6]]

    leads = LeadProspecto.all_tenants.filter(tenant=tenant)
    ctx['leads_total'] = leads.count()
    ctx['leads_novos'] = leads.filter(data_cadastro__gte=d30).count()

    vendas = (Venda.all_tenants.filter(tenant=tenant, data_venda__gte=d30)
              .aggregate(n=Count('id'), valor=Sum('valor')))
    ctx['vendas_qtd'] = vendas['n'] or 0
    ctx['vendas_valor'] = vendas['valor'] or 0

    clientes = ClienteHubsoft.all_tenants.filter(tenant=tenant, ativo=True)
    ctx['clientes_total'] = clientes.count()
    ctx['churn_risco'] = clientes.filter(churn_score__gte=70).count()

    abertos = ['aberto', 'em_andamento', 'aguardando_cliente']
    ctx['tickets_abertos'] = Ticket.all_tenants.filter(tenant=tenant, status__in=abertos).count()

    # --- Workspace ---
    from apps.workspace.models import Projeto, Tarefa
    ctx['projetos_ativos'] = list(
        Projeto.all_tenants.filter(tenant=tenant, ativo=True, status__in=['planejamento', 'em_andamento'])
        .order_by('-criado_em')[:6])
    tar = {t['status']: t['n'] for t in
           Tarefa.all_tenants.filter(tenant=tenant).values('status').annotate(n=Count('id'))}
    ctx['tarefas_por_status'] = [{'rotulo': lbl, 'n': tar.get(val, 0)} for val, lbl in TAREFA_STATUS_CHOICES]
    ctx['tarefas_abertas'] = tar.get('pendente', 0) + tar.get('em_andamento', 0)

    propostas = Proposta.all_tenants.filter(tenant=tenant, status='pendente').select_related('agente')
    ctx['propostas_pendentes'] = list(propostas.order_by('-criado_em')[:6])
    ctx['propostas_n'] = propostas.count()

    # --- Agentes por time (organograma da empresa de agentes) ---
    labels = dict(Agente.EQUIPE_CHOICES)
    ag = (Agente.all_tenants.filter(tenant=tenant, ativo=True)
          .values('equipe').annotate(n=Count('id')).order_by('-n'))
    ctx['agentes_por_time'] = [{'equipe': labels.get(a['equipe'], a['equipe'] or 'Sem time'), 'n': a['n']} for a in ag]
    ctx['agentes_total'] = sum(a['n'] for a in ag)

    # --- IA: agente CEO pro briefing executivo do cockpit ---
    ceo_ag = (Agente.all_tenants.filter(tenant=tenant, ativo=True, nome='CEO').first()
              or Agente.all_tenants.filter(tenant=tenant, ativo=True, equipe='executivo').first())
    ctx['ceo_agente_id'] = ceo_ag.pk if ceo_ag else None
    ctx['ceo_agente_nome'] = ceo_ag.nome if ceo_ag else ''

    return render(request, 'workspace/ceo.html', ctx)
