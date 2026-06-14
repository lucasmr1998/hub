"""
Painel de Contratos — /integracoes/contratos/.

Lista de tentativas de criar/aceitar contrato HubSoft (sucessos + falhas
+ pulados por idempotencia) por tenant, com detalhe e re-tentativa manual.
"""
import time
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Avg
from django.http import JsonResponse, Http404
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.integracoes.models import ContratoTentativa
from apps.sistema.decorators import user_tem_funcionalidade


def _checar_ver(request):
    return user_tem_funcionalidade(request, 'integracoes.ver_contratos')


def _checar_gerenciar(request):
    return user_tem_funcionalidade(request, 'integracoes.gerenciar_contratos')


@login_required
def lista_contratos(request):
    """Lista paginada + KPIs do dia + filtros."""
    if not _checar_ver(request):
        messages.error(request, 'Voce nao tem permissao para ver Contratos.')
        return redirect('dashboard:home')

    qs = ContratoTentativa.objects.all().select_related(
        'lead', 'cliente_hubsoft', 'oportunidade', 'integracao',
    )

    status_filtro = (request.GET.get('status') or '').strip()
    if status_filtro in ('sucesso', 'falha', 'pendente', 'pulado_idempotente'):
        qs = qs.filter(status=status_filtro)

    acao_filtro = (request.GET.get('acao') or '').strip()
    if acao_filtro in ('gerar', 'assinar'):
        qs = qs.filter(acao=acao_filtro)

    lead_filtro = (request.GET.get('lead') or '').strip()
    if lead_filtro:
        try:
            qs = qs.filter(lead_id=int(lead_filtro))
        except ValueError:
            qs = qs.filter(lead__nome_razaosocial__icontains=lead_filtro)

    data_de = (request.GET.get('data_de') or '').strip()
    data_ate = (request.GET.get('data_ate') or '').strip()
    if data_de:
        qs = qs.filter(criado_em__date__gte=data_de)
    if data_ate:
        qs = qs.filter(criado_em__date__lte=data_ate)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    # KPIs do dia (independente dos filtros)
    hoje = timezone.localdate()
    qs_hoje = ContratoTentativa.objects.filter(criado_em__date=hoje)
    total_hoje = qs_hoje.count()
    sucessos_hoje = qs_hoje.filter(status='sucesso').count()
    falhas_hoje = qs_hoje.filter(status='falha').count()
    pulados_hoje = qs_hoje.filter(status='pulado_idempotente').count()
    taxa_sucesso = round((sucessos_hoje / total_hoje) * 100, 1) if total_hoje else 0.0
    duracao_media = qs_hoje.filter(status='sucesso').aggregate(m=Avg('duracao_ms'))['m'] or 0

    top_motivos = list(
        qs_hoje.filter(status='falha')
        .values('motivo_falha_categoria')
        .annotate(n=Count('id'))
        .order_by('-n')[:3]
    )

    filter_fields = [
        {'type': 'select', 'label': 'Status', 'name': 'status', 'value': status_filtro,
         'options': [('', 'Todos'), ('sucesso', 'Sucesso'), ('falha', 'Falha'),
                     ('pulado_idempotente', 'Pulado'), ('pendente', 'Pendente')]},
        {'type': 'select', 'label': 'Acao', 'name': 'acao', 'value': acao_filtro,
         'options': [('', 'Todas'), ('gerar', 'Gerar'), ('assinar', 'Assinar')]},
        {'type': 'date', 'label': 'A partir de', 'name': 'data_de', 'value': data_de},
        {'type': 'date', 'label': 'Ate', 'name': 'data_ate', 'value': data_ate},
    ]

    return render(request, 'integracoes/contratos_lista.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'kpi_total': total_hoje,
        'kpi_sucessos': sucessos_hoje,
        'kpi_falhas': falhas_hoje,
        'kpi_pulados': pulados_hoje,
        'kpi_taxa_sucesso': taxa_sucesso,
        'kpi_duracao_media_ms': int(duracao_media),
        'kpi_top_motivos': top_motivos,
        'filtro_status': status_filtro,
        'filtro_acao': acao_filtro,
        'filtro_lead': lead_filtro,
        'filtro_data_de': data_de,
        'filtro_data_ate': data_ate,
        'filter_fields': filter_fields,
        'pode_gerenciar': _checar_gerenciar(request),
    })


@login_required
def detalhe_contrato(request, grupo_id):
    """Detalhe agrupado: todas as tentativas do mesmo lead/acao."""
    if not _checar_ver(request):
        messages.error(request, 'Voce nao tem permissao para ver Contratos.')
        return redirect('dashboard:home')

    try:
        grupo_uuid = uuid.UUID(str(grupo_id))
    except (ValueError, TypeError):
        raise Http404('grupo_id invalido')

    tentativas = list(
        ContratoTentativa.objects
        .filter(grupo_tentativas_id=grupo_uuid)
        .select_related('lead', 'cliente_hubsoft', 'servico', 'oportunidade', 'integracao', 'usuario_retry', 'regra_automacao')
        .order_by('tentativa_numero')
    )
    if not tentativas:
        raise Http404('Grupo de tentativas nao encontrado')

    primeira = tentativas[0]

    return render(request, 'integracoes/contratos_detalhe.html', {
        'tentativas': tentativas,
        'primeira': primeira,
        'grupo_id': grupo_uuid,
        'pode_gerenciar': _checar_gerenciar(request),
    })


@login_required
@require_POST
def retentar_contrato(request, grupo_id):
    """Re-tenta a ultima acao do grupo (gerar ou assinar). Idempotente — se o lead
    ja tem contrato_aceito, marca como pulado_idempotente sem chamar HubSoft."""
    if not _checar_gerenciar(request):
        return JsonResponse({'ok': False, 'error': 'Sem permissao para re-tentar.'}, status=403)

    try:
        grupo_uuid = uuid.UUID(str(grupo_id))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'grupo_id invalido'}, status=400)

    ultima = (
        ContratoTentativa.objects
        .filter(grupo_tentativas_id=grupo_uuid)
        .order_by('-tentativa_numero')
        .select_related('oportunidade', 'integracao')
        .first()
    )
    if not ultima:
        return JsonResponse({'ok': False, 'error': 'Grupo nao encontrado'}, status=404)
    if not ultima.oportunidade_id:
        return JsonResponse({'ok': False, 'error': 'Tentativa sem oportunidade vinculada'}, status=400)

    # Refresh da oportunidade (pega estado atual)
    from apps.comercial.crm.models import OportunidadeVenda
    try:
        oport = OportunidadeVenda.objects.select_related('lead').get(pk=ultima.oportunidade_id)
    except OportunidadeVenda.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Oportunidade nao encontrada'}, status=404)

    # Dispara a acao novamente (delega pro engine)
    from apps.comercial.crm.services.automacao_pipeline import (
        _acao_gerar_contrato_hubsoft, _acao_assinar_contrato_hubsoft,
    )
    acao_func = _acao_gerar_contrato_hubsoft if ultima.acao == 'gerar' else _acao_assinar_contrato_hubsoft

    # Marca origem da nova tentativa como retry_manual via context global temporario
    # — workaround: chama a acao e depois atualiza a tentativa mais nova do grupo
    t0 = time.monotonic()
    try:
        resultado = acao_func(oport, {})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': f'Erro ao executar: {exc}'}, status=500)

    # Pega a tentativa mais nova criada agora
    nova = (
        ContratoTentativa.objects
        .filter(grupo_tentativas_id=grupo_uuid)
        .order_by('-tentativa_numero').first()
    )
    if nova and nova.pk != ultima.pk:
        # Marca essa como retry manual
        nova.origem = 'retry_manual'
        nova.usuario_retry = request.user
        nova.save(update_fields=['origem', 'usuario_retry'])
        return JsonResponse({
            'ok': nova.status == 'sucesso',
            'tentativa_numero': nova.tentativa_numero,
            'status': nova.status,
            'categoria': nova.motivo_falha_categoria,
            'msg': nova.motivo_falha_mensagem[:300] if nova.motivo_falha_mensagem else '',
        })

    # Acao foi idempotente — nao criou nova tentativa, foi pulada
    return JsonResponse({
        'ok': resultado is not False,
        'status': 'pulado_idempotente',
        'msg': 'Acao pulada por idempotencia (lead ja tem contrato aceito).',
    })
