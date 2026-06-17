"""
Views do app relatorios — UI + APIs.

UI: lista de dashboards, detalhe (view), edicao (drag-drop GridStack).
APIs JSON pro builder: data sources, preview, dados de widget, salvar.

Permissoes:
- relatorios.ver_dashboards     — pra qualquer pagina
- relatorios.criar_dashboard    — criar/editar dashboard pessoal
- relatorios.compartilhar_dashboard — marcar como compartilhado
Superuser bypassa.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.sistema.decorators import user_tem_funcionalidade

from . import data_sources as ds_registry
from .models import Dashboard, Widget
from .query_builder import WidgetQueryBuilder, WidgetQueryError

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _perm(request, codigo: str) -> bool:
    if request.user.is_superuser:
        return True
    return user_tem_funcionalidade(request, codigo)


def _pode_editar_dashboard(request, dashboard: Dashboard) -> bool:
    if request.user.is_superuser:
        return True
    if dashboard.criado_por_id == request.user.id:
        return _perm(request, 'relatorios.criar_dashboard')
    # Outros usuarios so editam se forem admin (compartilhar_dashboard)
    return _perm(request, 'relatorios.compartilhar_dashboard')


def _dashboards_visiveis(request):
    """QuerySet de dashboards que o usuario pode ver."""
    return Dashboard.objects.filter(
        Q(compartilhado=True) | Q(criado_por=request.user)
    ).order_by('ordem', 'nome')


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------

@login_required
def lista_view(request):
    if not _perm(request, 'relatorios.ver_dashboards'):
        return HttpResponseForbidden('Sem permissao')
    dashboards = list(_dashboards_visiveis(request).select_related('criado_por'))
    proprios = [d for d in dashboards if d.criado_por_id == request.user.id]
    compartilhados = [d for d in dashboards if d.criado_por_id != request.user.id]
    return render(request, 'relatorios/lista.html', {
        'proprios': proprios,
        'compartilhados': compartilhados,
        'pode_criar': _perm(request, 'relatorios.criar_dashboard'),
        'page_title': 'Relatorios',
    })


@login_required
def dashboard_detalhe_view(request, pk):
    if not _perm(request, 'relatorios.ver_dashboards'):
        return HttpResponseForbidden('Sem permissao')
    dashboard = get_object_or_404(_dashboards_visiveis(request), pk=pk)
    widgets = list(dashboard.widgets.all().order_by('ordem', 'id'))
    return render(request, 'relatorios/dashboard_detalhe.html', {
        'dashboard': dashboard,
        'widgets': widgets,
        'pode_editar': _pode_editar_dashboard(request, dashboard),
        'modo_edicao': False,
        'page_title': dashboard.nome,
    })


@login_required
def dashboard_editar_view(request, pk):
    dashboard = get_object_or_404(Dashboard.objects.all(), pk=pk)
    if not _pode_editar_dashboard(request, dashboard):
        return HttpResponseForbidden('Sem permissao pra editar este dashboard')

    if request.method == 'POST':
        # Salva alteracoes basicas do dashboard
        nome = (request.POST.get('nome') or '').strip()
        descricao = (request.POST.get('descricao') or '').strip()
        compartilhado_flag = request.POST.get('compartilhado') == 'on'
        if nome:
            dashboard.nome = nome[:120]
        dashboard.descricao = descricao
        if _perm(request, 'relatorios.compartilhar_dashboard'):
            dashboard.compartilhado = compartilhado_flag
        dashboard.save()
        return redirect('relatorios:editar', pk=dashboard.pk)

    widgets = list(dashboard.widgets.all().order_by('ordem', 'id'))
    data_sources_list = [{
        'slug': d.slug,
        'label': d.label,
        'descricao': d.descricao,
    } for d in ds_registry.todos()]
    return render(request, 'relatorios/dashboard_detalhe.html', {
        'dashboard': dashboard,
        'widgets': widgets,
        'pode_editar': True,
        'modo_edicao': True,
        'data_sources': data_sources_list,
        'pode_compartilhar': _perm(request, 'relatorios.compartilhar_dashboard'),
        'page_title': f'{dashboard.nome} — Editar',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def dashboard_criar_view(request):
    if not _perm(request, 'relatorios.criar_dashboard'):
        return HttpResponseForbidden('Sem permissao pra criar dashboard')
    if request.method == 'GET':
        return render(request, 'relatorios/criar.html', {'page_title': 'Novo dashboard'})

    nome = (request.POST.get('nome') or '').strip()
    descricao = (request.POST.get('descricao') or '').strip()
    if not nome:
        return render(request, 'relatorios/criar.html', {
            'erro': 'Nome obrigatorio',
            'nome_pre': nome, 'descricao_pre': descricao,
        })
    dashboard = Dashboard.objects.create(
        nome=nome[:120],
        descricao=descricao,
        criado_por=request.user,
        compartilhado=False,
    )
    return redirect('relatorios:editar', pk=dashboard.pk)


@login_required
@require_POST
def dashboard_excluir_view(request, pk):
    dashboard = get_object_or_404(Dashboard.objects.all(), pk=pk)
    if not _pode_editar_dashboard(request, dashboard):
        return HttpResponseForbidden('Sem permissao')
    dashboard.delete()
    return redirect('relatorios:lista')


# ----------------------------------------------------------------------------
# APIs JSON pro builder
# ----------------------------------------------------------------------------

@login_required
@require_GET
def api_data_sources(request):
    """Lista todos data sources disponiveis pro builder."""
    if not _perm(request, 'relatorios.criar_dashboard'):
        return JsonResponse({'error': 'Sem permissao'}, status=403)
    fontes = [{
        'slug': d.slug,
        'label': d.label,
        'descricao': d.descricao,
        'metricas': d.metricas,
    } for d in ds_registry.todos()]
    return JsonResponse({'data_sources': fontes})


@login_required
@require_GET
def api_data_source_detalhe(request, slug):
    """Retorna campos + metricas + operadores pro wizard do widget."""
    if not _perm(request, 'relatorios.criar_dashboard'):
        return JsonResponse({'error': 'Sem permissao'}, status=403)
    ds = ds_registry.get(slug)
    if not ds:
        return JsonResponse({'error': f'Data source nao encontrado: {slug}'}, status=404)
    campos = []
    for nome, spec in (ds.campos or {}).items():
        campos.append({
            'nome': nome,
            'label': spec.label,
            'tipo': spec.tipo,
            'granularidades': spec.granularidades,
            'choices': spec.choices,
        })
    return JsonResponse({
        'slug': ds.slug,
        'label': ds.label,
        'descricao': ds.descricao,
        'campos': campos,
        'metricas': ds.metricas,
    })


@login_required
@require_POST
def api_preview(request):
    """
    Preview de widget sem persistir. Body JSON:
    {data_source, metrica, agrupamento, filtros, visualizacao}
    """
    if not _perm(request, 'relatorios.criar_dashboard'):
        return JsonResponse({'error': 'Sem permissao'}, status=403)
    try:
        body = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    # Widget "virtual" — usa o builder sem salvar no DB
    class _WidgetVirtual:
        data_source = body.get('data_source', '')
        metrica = body.get('metrica') or {'tipo': 'count'}
        agrupamento = body.get('agrupamento') or {}
        filtros = body.get('filtros') or []
        visualizacao = body.get('visualizacao', 'numero')

    try:
        builder = WidgetQueryBuilder(_WidgetVirtual(), tenant=request.tenant)
        resultado = builder.build()
        return JsonResponse({'ok': True, **resultado.to_dict()})
    except WidgetQueryError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        logger.exception('Preview falhou')
        return JsonResponse({'error': f'{type(exc).__name__}: {exc}'}, status=500)


@login_required
@require_GET
def api_widget_dados(request, pk):
    """Retorna dados de um widget salvo pra render no front."""
    if not _perm(request, 'relatorios.ver_dashboards'):
        return JsonResponse({'error': 'Sem permissao'}, status=403)
    widget = get_object_or_404(Widget.objects.select_related('dashboard'), pk=pk)
    # Filtra acesso pelo dashboard
    dashboard = widget.dashboard
    if not (dashboard.compartilhado or dashboard.criado_por_id == request.user.id or request.user.is_superuser):
        return JsonResponse({'error': 'Sem acesso a este dashboard'}, status=403)
    try:
        builder = WidgetQueryBuilder(widget, tenant=request.tenant)
        resultado = builder.build()
        return JsonResponse({'ok': True, 'widget_id': widget.pk, **resultado.to_dict()})
    except WidgetQueryError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        logger.exception('api_widget_dados falhou (widget=%s)', pk)
        return JsonResponse({'error': f'{type(exc).__name__}: {exc}'}, status=500)


@login_required
@require_GET
def api_widget_config(request, pk):
    """Retorna config completa do widget pra pre-popular o wizard de edicao."""
    if not _perm(request, 'relatorios.ver_dashboards'):
        return JsonResponse({'error': 'Sem permissao'}, status=403)
    widget = get_object_or_404(Widget.objects.select_related('dashboard'), pk=pk)
    dashboard = widget.dashboard
    if not (dashboard.compartilhado or dashboard.criado_por_id == request.user.id or request.user.is_superuser):
        return JsonResponse({'error': 'Sem acesso'}, status=403)
    return JsonResponse({
        'ok': True,
        'widget': {
            'id': widget.pk,
            'titulo': widget.titulo,
            'data_source': widget.data_source,
            'metrica': widget.metrica or {'tipo': 'count'},
            'agrupamento': widget.agrupamento or {},
            'filtros': widget.filtros or [],
            'visualizacao': widget.visualizacao or 'numero',
        },
    })


@login_required
@require_POST
def api_widget_salvar(request):
    """
    Cria ou atualiza widget. Body JSON:
    {id?, dashboard_id, titulo, data_source, metrica, agrupamento, filtros, visualizacao, layout?}
    """
    if not _perm(request, 'relatorios.criar_dashboard'):
        return JsonResponse({'error': 'Sem permissao'}, status=403)
    try:
        body = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    dashboard_id = body.get('dashboard_id')
    dashboard = get_object_or_404(Dashboard.objects.all(), pk=dashboard_id)
    if not _pode_editar_dashboard(request, dashboard):
        return JsonResponse({'error': 'Sem permissao pra editar este dashboard'}, status=403)

    widget_id = body.get('id')
    if widget_id:
        widget = get_object_or_404(Widget.objects.all(), pk=widget_id, dashboard=dashboard)
    else:
        widget = Widget(dashboard=dashboard)

    widget.titulo = (body.get('titulo') or 'Widget')[:120]
    widget.data_source = body.get('data_source') or ''
    widget.metrica = body.get('metrica') or {'tipo': 'count'}
    widget.agrupamento = body.get('agrupamento') or {}
    widget.filtros = body.get('filtros') or []
    widget.visualizacao = body.get('visualizacao') or 'numero'
    if body.get('layout'):
        widget.layout = body['layout']
    if body.get('config_extra'):
        widget.config_extra = body['config_extra']
    widget.save()
    return JsonResponse({'ok': True, 'widget_id': widget.pk, 'criado': not bool(widget_id)})


@login_required
@require_POST
def api_widget_excluir(request, pk):
    widget = get_object_or_404(Widget.objects.select_related('dashboard'), pk=pk)
    if not _pode_editar_dashboard(request, widget.dashboard):
        return JsonResponse({'error': 'Sem permissao'}, status=403)
    widget.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_dashboard_layout(request, pk):
    """
    Salva layout do GridStack (drag-drop).
    Body: {layouts: [{id: widget_id, x, y, w, h}, ...]}
    """
    dashboard = get_object_or_404(Dashboard.objects.all(), pk=pk)
    if not _pode_editar_dashboard(request, dashboard):
        return JsonResponse({'error': 'Sem permissao'}, status=403)
    try:
        body = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)
    layouts = body.get('layouts') or []
    widgets_map = {w.pk: w for w in dashboard.widgets.all()}
    for item in layouts:
        wid = item.get('id')
        w = widgets_map.get(wid)
        if not w:
            continue
        w.layout = {
            'x': int(item.get('x') or 0),
            'y': int(item.get('y') or 0),
            'w': int(item.get('w') or 4),
            'h': int(item.get('h') or 3),
        }
        w.save(update_fields=['layout', 'atualizado_em'])
    return JsonResponse({'ok': True, 'total': len(layouts)})
