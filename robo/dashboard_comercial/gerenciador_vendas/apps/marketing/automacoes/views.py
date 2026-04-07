import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.sistema.decorators import user_tem_funcionalidade

from .models import (
    RegraAutomacao, LogExecucao,
    NodoFluxo, ConexaoNodo, ExecucaoPendente,
)


def _check_perm(request, codigo):
    if not user_tem_funcionalidade(request, codigo):
        return JsonResponse({'error': 'Sem permissão para esta ação'}, status=403)
    return None


@login_required
def lista_automacoes(request):
    """Lista de automações configuradas pelo tenant."""
    denied = _check_perm(request, 'marketing.ver_automacoes')
    if denied: return denied
    regras = RegraAutomacao.objects.all().prefetch_related('condicoes', 'acoes')

    hoje = timezone.now().date()
    execucoes_hoje = LogExecucao.objects.filter(data_execucao__date=hoje).count()

    total_ativas = regras.filter(ativa=True).count()
    total_pausadas = regras.filter(ativa=False).count()
    total_exec = sum(r.total_execucoes for r in regras)
    total_suc = sum(r.total_sucesso for r in regras)
    taxa_sucesso = round(total_suc / total_exec * 100) if total_exec > 0 else 100

    context = {
        'regras': regras,
        'total_ativas': total_ativas,
        'total_pausadas': total_pausadas,
        'execucoes_hoje': execucoes_hoje,
        'taxa_sucesso': taxa_sucesso,
    }
    return render(request, 'automacoes/lista.html', context)


@login_required
def criar_automacao(request):
    """Criar nova automação."""
    denied = _check_perm(request, 'marketing.gerenciar_automacoes')
    if denied: return denied
    if request.method == 'POST':
        return _salvar_automacao(request)
    return render(request, 'automacoes/criar.html')


@login_required
def editar_automacao(request, pk):
    """Editar automação existente."""
    regra = get_object_or_404(RegraAutomacao, pk=pk)
    if request.method == 'POST':
        return _salvar_automacao(request, regra)

    return render(request, 'automacoes/criar.html', {'regra': regra})


def _salvar_automacao(request, regra=None):
    """Salva ou atualiza uma regra de automação (apenas nome/descrição, resto no editor visual)."""
    tenant = request.tenant
    is_new = regra is None

    if is_new:
        regra = RegraAutomacao(tenant=tenant, criado_por=request.user, modo_fluxo=True)

    regra.nome = request.POST.get('nome', '').strip()
    regra.descricao = request.POST.get('descricao', '').strip()
    regra.save()

    # Nova automação → redireciona para o editor visual
    if is_new:
        return redirect('marketing_automacoes:editor_fluxo', pk=regra.pk)

    return redirect('marketing_automacoes:lista')


@login_required
@require_POST
def toggle_automacao(request, pk):
    """Ativar/desativar automação via AJAX."""
    denied = _check_perm(request, 'marketing.gerenciar_automacoes')
    if denied: return denied
    regra = get_object_or_404(RegraAutomacao, pk=pk)
    regra.ativa = not regra.ativa
    regra.save(update_fields=['ativa'])
    return JsonResponse({'ok': True, 'ativa': regra.ativa})


@login_required
@require_POST
def excluir_automacao(request, pk):
    """Excluir automação."""
    denied = _check_perm(request, 'marketing.gerenciar_automacoes')
    if denied: return denied
    regra = get_object_or_404(RegraAutomacao, pk=pk)
    regra.delete()
    return redirect('marketing_automacoes:lista')


@login_required
def historico_automacao(request, pk):
    """Histórico de execuções de uma automação."""
    regra = get_object_or_404(RegraAutomacao, pk=pk)
    logs = regra.logs.select_related('acao', 'nodo', 'lead').all()[:50]

    return render(request, 'automacoes/historico.html', {
        'regra': regra,
        'logs': logs,
    })


# ============================================================================
# EDITOR VISUAL (Drawflow)
# ============================================================================

@login_required
def editor_fluxo(request, pk):
    """Editor visual de fluxograma com Drawflow."""
    regra = get_object_or_404(RegraAutomacao, pk=pk)

    # Se nao tem fluxo_json mas tem nodos no banco, montar para reconstruir
    nodos_db = []
    conexoes_db = []
    if not regra.fluxo_json:
        for nodo in regra.nodos.all().order_by('ordem'):
            nodos_db.append({
                'id': nodo.id,
                'tipo': nodo.tipo,
                'subtipo': nodo.subtipo,
                'nome': nodo.subtipo.replace('_', ' ').title() if nodo.subtipo else nodo.get_tipo_display(),
                'config': nodo.configuracao,
                'pos_x': nodo.pos_x,
                'pos_y': nodo.pos_y,
            })
        for conn in regra.conexoes.all():
            conexoes_db.append({
                'origem': conn.nodo_origem_id,
                'destino': conn.nodo_destino_id,
                'tipo_saida': conn.tipo_saida,
            })

    # Dados do banco para selects dinamicos
    from apps.comercial.crm.models import Pipeline, PipelineEstagio, SegmentoCRM
    from django.contrib.auth.models import User

    pipelines = list(Pipeline.objects.values('id', 'nome', 'slug'))
    estagios = list(PipelineEstagio.objects.values('id', 'nome', 'slug', 'pipeline_id', 'ordem').order_by('pipeline_id', 'ordem'))
    usuarios = list(User.objects.filter(is_staff=True, is_active=True).values('id', 'username', 'first_name', 'last_name'))
    segmentos = list(SegmentoCRM.objects.values('id', 'nome'))

    return render(request, 'automacoes/editor_fluxo.html', {
        'regra': regra,
        'fluxo_json': json.dumps(regra.fluxo_json) if regra.fluxo_json else '{}',
        'nodos_db': json.dumps(nodos_db),
        'conexoes_db': json.dumps(conexoes_db),
        'pipelines_json': json.dumps(pipelines),
        'estagios_json': json.dumps(estagios),
        'usuarios_json': json.dumps(usuarios),
        'segmentos_json': json.dumps(segmentos),
    })


@login_required
@require_POST
def salvar_fluxo(request, pk):
    """Salva o fluxograma: persiste nodos e conexões no banco."""
    regra = get_object_or_404(RegraAutomacao, pk=pk)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    # Salvar estado bruto do Drawflow para re-import
    regra.fluxo_json = data.get('drawflow_state', {})
    regra.modo_fluxo = True
    regra.save(update_fields=['fluxo_json', 'modo_fluxo'])

    # Recriar nodos e conexões
    regra.nodos.all().delete()
    regra.conexoes.all().delete()

    id_map = {}  # temp_id → NodoFluxo
    for nodo_data in data.get('nodos', []):
        nodo = NodoFluxo.objects.create(
            tenant=regra.tenant, regra=regra,
            tipo=nodo_data.get('tipo', 'action'),
            subtipo=nodo_data.get('subtipo', ''),
            configuracao=nodo_data.get('config', {}),
            pos_x=nodo_data.get('pos_x', 0),
            pos_y=nodo_data.get('pos_y', 0),
            ordem=nodo_data.get('ordem', 0),
        )
        id_map[str(nodo_data.get('id_temp', nodo_data.get('id', '')))] = nodo

    for conn_data in data.get('conexoes', []):
        origem = id_map.get(str(conn_data.get('origem')))
        destino = id_map.get(str(conn_data.get('destino')))
        if origem and destino:
            ConexaoNodo.objects.create(
                tenant=regra.tenant, regra=regra,
                nodo_origem=origem, nodo_destino=destino,
                tipo_saida=conn_data.get('tipo_saida', 'default'),
            )

    return JsonResponse({'ok': True, 'nodos': len(id_map)})


# ============================================================================
# DASHBOARD CENTRAL DE AUTOMAÇÕES
# ============================================================================

@login_required
def dashboard_automacoes(request):
    """Dashboard central com métricas e logs de automações."""
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    from datetime import timedelta

    hoje = timezone.now().date()
    semana = hoje - timedelta(days=7)
    mes = hoje - timedelta(days=30)

    logs_hoje = LogExecucao.objects.filter(data_execucao__date=hoje)
    total_hoje = logs_hoje.count()
    sucesso_hoje = logs_hoje.filter(status='sucesso').count()
    taxa = round(sucesso_hoje / total_hoje * 100) if total_hoje else 100

    regras_ativas = RegraAutomacao.objects.filter(ativa=True).count()
    pendentes = ExecucaoPendente.objects.filter(status='pendente').count()

    # Gráfico: execuções últimos 30 dias
    chart_data = list(
        LogExecucao.objects.filter(data_execucao__date__gte=mes)
        .annotate(dia=TruncDate('data_execucao'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )
    chart_labels = [(mes + timedelta(days=i)).strftime('%d/%m') for i in range(31)]
    chart_dict = {str(d['dia']): d['total'] for d in chart_data}
    chart_values = [chart_dict.get(str(mes + timedelta(days=i)), 0) for i in range(31)]

    # Top regras
    top_regras = RegraAutomacao.objects.filter(ativa=True).order_by('-total_execucoes')[:10]

    # Erros recentes
    erros_recentes = LogExecucao.objects.filter(status='erro').select_related('regra', 'lead').order_by('-data_execucao')[:10]

    # Logs filtráveis
    logs = LogExecucao.objects.all().select_related('regra', 'acao', 'nodo', 'lead').order_by('-data_execucao')[:100]

    return render(request, 'automacoes/dashboard.html', {
        'total_hoje': total_hoje,
        'taxa_sucesso': taxa,
        'regras_ativas': regras_ativas,
        'pendentes': pendentes,
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
        'top_regras': top_regras,
        'erros_recentes': erros_recentes,
        'logs': logs,
    })


# ============================================================================
# TIMELINE DO LEAD (API JSON)
# ============================================================================

@login_required
def api_lead_timeline(request, lead_pk):
    """Retorna logs de automação para um lead específico (usado pelo CRM)."""
    logs = LogExecucao.objects.filter(lead_id=lead_pk).select_related('regra', 'acao', 'nodo').order_by('-data_execucao')[:30]

    resultado = []
    for log in logs:
        resultado.append({
            'id': log.pk,
            'regra': log.regra.nome,
            'acao': log.acao.get_tipo_display() if log.acao else (log.nodo.subtipo if log.nodo else ''),
            'status': log.status,
            'resultado': log.resultado[:100] if log.resultado else '',
            'data': log.data_execucao.strftime('%d/%m/%Y %H:%M'),
        })

    return JsonResponse({'logs': resultado})
