"""View unificada de logs com 4 tabs (Sistema, Integracao, Webhook N8N,
Fluxo Atendimento). Substitui a antiga logs_view que cobria so LogSistema.

Tabs:
- sistema:    LogSistema (categoria, acao, nivel, busca)
- integracao: LogIntegracao (integracao, metodo, sucesso, status_code)
- webhook:    LogWebhookN8N (acao, sucesso)
- fluxo:      LogFluxoAtendimento (status, atendimento)

Filtros comuns:
- tenant (slug)
- intervalo de data (data_de, data_ate)
- busca livre

Suporta export CSV via ?export=csv (limite 5000 linhas).
Paginacao: 100 por pagina via ?page=N.
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)


def _superuser_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_superuser)(view_func))


TABS_VALIDAS = ('sistema', 'integracao', 'webhook', 'fluxo')
LIMITE_EXPORT_CSV = 5000
PAGE_SIZE = 100


def _parse_intervalo(request):
    """Retorna (data_de, data_ate) como datetime aware ou None."""
    data_de = request.GET.get('data_de') or ''
    data_ate = request.GET.get('data_ate') or ''
    tz = timezone.get_current_timezone()

    def _parse(s, fim_do_dia=False):
        if not s:
            return None
        try:
            dt = datetime.strptime(s, '%Y-%m-%d')
            if fim_do_dia:
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=tz)
        except (ValueError, TypeError):
            return None

    return _parse(data_de), _parse(data_ate, fim_do_dia=True)


def _filtrar_tenant(qs, slug):
    if not slug or not hasattr(qs.model, 'tenant'):
        return qs
    from apps.sistema.models import Tenant
    t = Tenant.objects.filter(slug=slug).first()
    return qs.filter(tenant=t) if t else qs


def _tabs_disponiveis(request):
    """Conta total de logs por tab pra mostrar nos badges das tabs."""
    from apps.sistema.models import LogSistema
    from apps.integracoes.models import LogIntegracao

    counts = {}
    try:
        counts['sistema'] = LogSistema.all_tenants.count()
    except Exception:
        counts['sistema'] = 0
    try:
        counts['integracao'] = LogIntegracao.all_tenants.count()
    except Exception:
        counts['integracao'] = 0
    try:
        from apps.integracoes.models_audit import LogWebhookN8N
        counts['webhook'] = LogWebhookN8N.objects.count()
    except Exception:
        counts['webhook'] = 0
    try:
        from apps.comercial.atendimento.models import LogFluxoAtendimento
        counts['fluxo'] = LogFluxoAtendimento.all_tenants.count()
    except Exception:
        counts['fluxo'] = 0
    return counts


def _qs_sistema(request):
    from apps.sistema.models import LogSistema
    qs = LogSistema.all_tenants.all().select_related('tenant')
    qs = _filtrar_tenant(qs, request.GET.get('tenant'))
    nivel = request.GET.get('nivel')
    categoria = request.GET.get('categoria')
    acao = request.GET.get('acao')
    busca = request.GET.get('q')
    data_de, data_ate = _parse_intervalo(request)
    if nivel:
        qs = qs.filter(nivel=nivel)
    if categoria:
        qs = qs.filter(categoria=categoria)
    if acao:
        qs = qs.filter(acao=acao)
    if busca:
        qs = qs.filter(mensagem__icontains=busca)
    if data_de:
        qs = qs.filter(data_criacao__gte=data_de)
    if data_ate:
        qs = qs.filter(data_criacao__lte=data_ate)
    return qs.order_by('-data_criacao')


def _qs_integracao(request):
    from apps.integracoes.models import LogIntegracao
    qs = LogIntegracao.all_tenants.all().select_related('tenant', 'integracao')
    qs = _filtrar_tenant(qs, request.GET.get('tenant'))
    sucesso = request.GET.get('sucesso')
    metodo = request.GET.get('metodo')
    integracao_id = request.GET.get('integracao')
    status_code = request.GET.get('status_code')
    busca = request.GET.get('q')
    data_de, data_ate = _parse_intervalo(request)
    if sucesso == 'sim':
        qs = qs.filter(sucesso=True)
    elif sucesso == 'nao':
        qs = qs.filter(sucesso=False)
    if metodo:
        qs = qs.filter(metodo=metodo)
    if integracao_id:
        qs = qs.filter(integracao_id=integracao_id)
    if status_code:
        try:
            qs = qs.filter(status_code=int(status_code))
        except (ValueError, TypeError):
            pass
    if busca:
        from django.db.models import Q
        qs = qs.filter(Q(endpoint__icontains=busca) | Q(mensagem_erro__icontains=busca))
    if data_de:
        qs = qs.filter(data_criacao__gte=data_de)
    if data_ate:
        qs = qs.filter(data_criacao__lte=data_ate)
    return qs.order_by('-data_criacao')


def _qs_webhook(request):
    # LogWebhookN8N nao tem TenantMixin (cross-tenant). Campos: endpoint,
    # metodo, status_code, duracao_ms, ip_origem, user_agent, body_preview,
    # criado_em. Sem `sucesso` ou `tenant` aqui — "sucesso" eh deduzido do
    # status_code (2xx = sucesso).
    from apps.integracoes.models_audit import LogWebhookN8N
    qs = LogWebhookN8N.objects.all()
    sucesso = request.GET.get('sucesso')
    status_code = request.GET.get('status_code')
    metodo = request.GET.get('metodo')
    busca = request.GET.get('q')
    data_de, data_ate = _parse_intervalo(request)
    if sucesso == 'sim':
        qs = qs.filter(status_code__gte=200, status_code__lt=300)
    elif sucesso == 'nao':
        from django.db.models import Q
        qs = qs.filter(Q(status_code__lt=200) | Q(status_code__gte=300))
    if status_code:
        try:
            qs = qs.filter(status_code=int(status_code))
        except (ValueError, TypeError):
            pass
    if metodo:
        qs = qs.filter(metodo=metodo)
    if busca:
        from django.db.models import Q
        qs = qs.filter(Q(endpoint__icontains=busca) | Q(body_preview__icontains=busca))
    if data_de:
        qs = qs.filter(criado_em__gte=data_de)
    if data_ate:
        qs = qs.filter(criado_em__lte=data_ate)
    return qs.order_by('-criado_em')


def _qs_fluxo(request):
    from apps.comercial.atendimento.models import LogFluxoAtendimento
    qs = LogFluxoAtendimento.all_tenants.all().select_related('tenant', 'atendimento', 'nodo', 'lead')
    qs = _filtrar_tenant(qs, request.GET.get('tenant'))
    status = request.GET.get('status')
    busca = request.GET.get('q')
    data_de, data_ate = _parse_intervalo(request)
    if status:
        qs = qs.filter(status=status)
    if busca:
        qs = qs.filter(mensagem__icontains=busca)
    if data_de:
        qs = qs.filter(data_execucao__gte=data_de)
    if data_ate:
        qs = qs.filter(data_execucao__lte=data_ate)
    return qs.order_by('-data_execucao')


_TAB_QUERY = {
    'sistema':    _qs_sistema,
    'integracao': _qs_integracao,
    'webhook':    _qs_webhook,
    'fluxo':      _qs_fluxo,
}


def _exportar_csv(qs, tab):
    """Gera response CSV com ate LIMITE_EXPORT_CSV linhas."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="logs_{tab}_{timezone.now():%Y%m%d_%H%M}.csv"'
    )
    writer = csv.writer(response)

    if tab == 'sistema':
        writer.writerow(['data', 'tenant', 'nivel', 'categoria', 'acao', 'entidade', 'entidade_id', 'usuario', 'mensagem'])
        for lg in qs[:LIMITE_EXPORT_CSV]:
            writer.writerow([
                lg.data_criacao.strftime('%Y-%m-%d %H:%M:%S'),
                lg.tenant.slug if lg.tenant_id else '',
                lg.nivel, lg.categoria, lg.acao, lg.entidade, lg.entidade_id or '',
                lg.usuario or '', (lg.mensagem or '')[:500],
            ])
    elif tab == 'integracao':
        writer.writerow(['data', 'tenant', 'integracao', 'metodo', 'endpoint', 'status_code', 'sucesso', 'tempo_ms', 'erro'])
        for lg in qs[:LIMITE_EXPORT_CSV]:
            writer.writerow([
                lg.data_criacao.strftime('%Y-%m-%d %H:%M:%S'),
                lg.tenant.slug if lg.tenant_id else '',
                lg.integracao.nome if lg.integracao_id else '',
                lg.metodo, lg.endpoint, lg.status_code or '', lg.sucesso,
                lg.tempo_resposta_ms or '', (lg.mensagem_erro or '')[:500],
            ])
    elif tab == 'webhook':
        writer.writerow(['data', 'metodo', 'endpoint', 'status_code', 'duracao_ms', 'ip_origem', 'body_preview'])
        for lg in qs[:LIMITE_EXPORT_CSV]:
            writer.writerow([
                lg.criado_em.strftime('%Y-%m-%d %H:%M:%S'),
                lg.metodo, lg.endpoint, lg.status_code, lg.duracao_ms,
                lg.ip_origem or '', (lg.body_preview or '')[:500],
            ])
    elif tab == 'fluxo':
        writer.writerow(['data', 'tenant', 'atendimento', 'nodo', 'lead', 'tipo_nodo', 'status', 'mensagem'])
        for lg in qs[:LIMITE_EXPORT_CSV]:
            writer.writerow([
                lg.data_execucao.strftime('%Y-%m-%d %H:%M:%S'),
                lg.tenant.slug if lg.tenant_id else '',
                lg.atendimento_id, lg.nodo_id or '', lg.lead_id or '',
                lg.tipo_nodo, lg.status, (lg.mensagem or '')[:500],
            ])
    return response


@_superuser_required
def logs_view(request):
    """Pagina unificada de logs com 4 tabs."""
    from apps.sistema.models import Tenant

    tab = request.GET.get('tab', 'sistema')
    if tab not in TABS_VALIDAS:
        tab = 'sistema'

    qs = _TAB_QUERY[tab](request)

    # Export CSV antes da paginacao
    if request.GET.get('export') == 'csv':
        return _exportar_csv(qs, tab)

    paginator = Paginator(qs, PAGE_SIZE)
    pagina = paginator.get_page(request.GET.get('page'))

    # Opcoes pros filtros
    tenants = list(Tenant.objects.filter(ativo=True).order_by('slug').values_list('slug', flat=True))
    integracoes = []
    if tab == 'integracao':
        from apps.integracoes.models import IntegracaoAPI
        integracoes = list(
            IntegracaoAPI.all_tenants.all().order_by('nome').values('id', 'nome', 'tipo')
        )

    return render(request, 'admin_aurora/logs.html', {
        'tab': tab,
        'tabs_counts': _tabs_disponiveis(request),
        'pagina': pagina,
        'total': paginator.count,
        'page_size': PAGE_SIZE,
        'tenants_choices': tenants,
        'integracoes_choices': integracoes,
        # filtros atuais pra renderizar no form
        'f_tenant':     request.GET.get('tenant') or '',
        'f_busca':      request.GET.get('q') or '',
        'f_data_de':    request.GET.get('data_de') or '',
        'f_data_ate':   request.GET.get('data_ate') or '',
        'f_nivel':      request.GET.get('nivel') or '',
        'f_categoria':  request.GET.get('categoria') or '',
        'f_acao':       request.GET.get('acao') or '',
        'f_sucesso':    request.GET.get('sucesso') or '',
        'f_metodo':     request.GET.get('metodo') or '',
        'f_integracao': request.GET.get('integracao') or '',
        'f_status_code': request.GET.get('status_code') or '',
        'f_status':     request.GET.get('status') or '',
    })
