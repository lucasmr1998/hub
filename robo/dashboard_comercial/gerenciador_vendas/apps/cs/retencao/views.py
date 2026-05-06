"""
Views do módulo Retenção (CS).

Funcionalidade migrada de apps/comercial/crm/views.py em 05/05/2026 —
retenção é responsabilidade de Customer Success, não Comercial.

O modelo AlertaRetencao continua em apps.comercial.crm.models pra evitar
migration de dados. Acesso via import direto (cross-app é OK).
"""
import json
import re
from datetime import date as date_type, datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.sistema.utils import auditar


@login_required
def retencao_view(request):
    from apps.comercial.crm.models import AlertaRetencao

    alertas = AlertaRetencao.objects.filter(
        status__in=['novo', 'em_tratamento']
    ).select_related('cliente_hubsoft', 'responsavel', 'lead').order_by('-score_churn')

    context = {
        'alertas': alertas,
        'alertas_criticos': alertas.filter(nivel_risco='critico'),
        'alertas_altos': alertas.filter(nivel_risco='alto'),
        'alertas_medios': alertas.filter(nivel_risco='medio'),
        'alertas_baixos': alertas.filter(nivel_risco='baixo'),
        'page_title': 'Retenção de Clientes',
    }
    return render(request, 'retencao/retencao.html', context)


@login_required
@require_POST
@auditar('cs', 'tratar', 'alerta_retencao')
def api_tratar_alerta(request, pk):
    from apps.comercial.crm.models import AlertaRetencao

    alerta = get_object_or_404(AlertaRetencao, pk=pk)
    alerta.status = 'em_tratamento'
    alerta.responsavel = request.user
    alerta.save(update_fields=['status', 'responsavel'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
@auditar('cs', 'resolver', 'alerta_retencao')
def api_resolver_alerta(request, pk):
    from apps.comercial.crm.models import AlertaRetencao

    alerta = get_object_or_404(AlertaRetencao, pk=pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    alerta.status = 'resolvido'
    alerta.data_resolucao = timezone.now()
    alerta.acoes_tomadas = data.get('acoes_tomadas', '')
    alerta.save(update_fields=['status', 'data_resolucao', 'acoes_tomadas'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_scanner_retencao(request):
    """Executa scan de churn risk nos clientes Hubsoft."""
    from apps.comercial.crm.models import AlertaRetencao

    try:
        from apps.integracoes.models import ServicoClienteHubsoft  # noqa
    except ImportError:
        return JsonResponse({'ok': False, 'erro': 'App integracoes não disponível'}, status=500)

    hoje = timezone.now().date()
    criados = 0
    atualizados = 0

    servicos = ServicoClienteHubsoft.objects.exclude(
        data_fim_contrato=''
    ).select_related('cliente')

    for servico in servicos:
        raw = servico.data_fim_contrato.strip()
        data_fim = None
        try:
            if re.match(r'\d{4}-\d{2}-\d{2}', raw):
                data_fim = date_type.fromisoformat(raw[:10])
            elif re.match(r'\d{2}/\d{2}/\d{4}', raw):
                data_fim = datetime.strptime(raw[:10], '%d/%m/%Y').date()
        except (ValueError, TypeError):
            continue

        if not data_fim or data_fim < hoje:
            continue

        dias_restantes = (data_fim - hoje).days

        if dias_restantes <= 30:
            nivel, score_base = 'critico', 90
        elif dias_restantes <= 60:
            nivel, score_base = 'alto', 70
        elif dias_restantes <= 90:
            nivel, score_base = 'medio', 50
        else:
            continue

        cliente = servico.cliente
        alerta = AlertaRetencao.objects.filter(
            cliente_hubsoft=cliente,
            tipo_alerta='contrato_expirando',
            status__in=['novo', 'em_tratamento'],
        ).first()

        if alerta:
            atualizados += 1
        else:
            AlertaRetencao.objects.create(
                cliente_hubsoft=cliente,
                lead=cliente.lead,
                tipo_alerta='contrato_expirando',
                nivel_risco=nivel,
                score_churn=max(0, score_base - dias_restantes),
                descricao=f'Contrato expira em {dias_restantes} dias ({data_fim.strftime("%d/%m/%Y")})',
                data_expiracao_contrato=data_fim,
            )
            criados += 1

    return JsonResponse({'ok': True, 'criados': criados, 'atualizados': atualizados})
