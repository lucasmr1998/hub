"""
Painel de Ordens de Servico — /integracoes/ordens-servico/.

Lista de tentativas (sucessos + falhas) por tenant + detalhe agrupado por
id_atendimento_hubsoft + re-tentativa manual com slot/tecnico diferente.
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

from apps.integracoes.models import OrdemServicoTentativa
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.integracoes.services.hubsoft_errors import categorizar_falha_hubsoft
from apps.sistema.decorators import user_tem_funcionalidade


def _checar_ver(request):
    return user_tem_funcionalidade(request, 'integracoes.ver_ordens_servico')


def _checar_gerenciar(request):
    return user_tem_funcionalidade(request, 'integracoes.gerenciar_ordens_servico')


@login_required
def lista_ordens_servico(request):
    """Lista + KPIs do dia + filtros."""
    if not _checar_ver(request):
        messages.error(request, 'Voce nao tem permissao para ver Ordens de Servico.')
        return redirect('dashboard:home')

    qs = OrdemServicoTentativa.objects.all().select_related(
        'lead', 'cliente_hubsoft', 'integracao',
    )

    # Filtros
    status_filtro = (request.GET.get('status') or '').strip()
    if status_filtro in ('sucesso', 'falha', 'pendente'):
        qs = qs.filter(status=status_filtro)

    cidade_filtro = (request.GET.get('cidade') or '').strip()
    if cidade_filtro:
        qs = qs.filter(cidade__icontains=cidade_filtro)

    tecnico_filtro = (request.GET.get('tecnico') or '').strip()
    if tecnico_filtro:
        try:
            qs = qs.filter(id_tecnico=int(tecnico_filtro))
        except ValueError:
            qs = qs.filter(tecnico_nome__icontains=tecnico_filtro)

    data_de = (request.GET.get('data_de') or '').strip()
    data_ate = (request.GET.get('data_ate') or '').strip()
    if data_de:
        qs = qs.filter(criado_em__date__gte=data_de)
    if data_ate:
        qs = qs.filter(criado_em__date__lte=data_ate)

    # Pagina
    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    # KPIs do dia (independente dos filtros, usa CURRENT_DATE)
    hoje = timezone.localdate()
    qs_hoje = OrdemServicoTentativa.objects.filter(criado_em__date=hoje)
    total_hoje = qs_hoje.count()
    sucessos_hoje = qs_hoje.filter(status='sucesso').count()
    falhas_hoje = qs_hoje.filter(status='falha').count()
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
         'options': [('', 'Todos'), ('sucesso', 'Sucesso'), ('falha', 'Falha'), ('pendente', 'Pendente')]},
        {'type': 'text', 'label': 'Tecnico (id ou nome)', 'name': 'tecnico', 'value': tecnico_filtro, 'placeholder': 'ex: 139'},
        {'type': 'date', 'label': 'A partir de', 'name': 'data_de', 'value': data_de},
        {'type': 'date', 'label': 'Ate', 'name': 'data_ate', 'value': data_ate},
    ]

    return render(request, 'integracoes/ordens_servico_lista.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'kpi_total': total_hoje,
        'kpi_sucessos': sucessos_hoje,
        'kpi_falhas': falhas_hoje,
        'kpi_taxa_sucesso': taxa_sucesso,
        'kpi_duracao_media_ms': int(duracao_media),
        'kpi_top_motivos': top_motivos,
        'filtro_status': status_filtro,
        'filtro_cidade': cidade_filtro,
        'filtro_tecnico': tecnico_filtro,
        'filtro_data_de': data_de,
        'filtro_data_ate': data_ate,
        'filter_fields': filter_fields,
        'pode_gerenciar': _checar_gerenciar(request),
    })


@login_required
def detalhe_ordem_servico(request, grupo_id):
    """Detalhe: todas as tentativas do mesmo id_atendimento_hubsoft."""
    if not _checar_ver(request):
        messages.error(request, 'Voce nao tem permissao para ver Ordens de Servico.')
        return redirect('dashboard:home')

    try:
        grupo_uuid = uuid.UUID(str(grupo_id))
    except (ValueError, TypeError):
        raise Http404('grupo_id invalido')

    tentativas = list(
        OrdemServicoTentativa.objects
        .filter(grupo_tentativas_id=grupo_uuid)
        .select_related('lead', 'cliente_hubsoft', 'servico', 'integracao', 'usuario_retry')
        .order_by('tentativa_numero')
    )
    if not tentativas:
        raise Http404('Grupo de tentativas nao encontrado')

    primeira = tentativas[0]

    return render(request, 'integracoes/ordens_servico_detalhe.html', {
        'tentativas': tentativas,
        'primeira': primeira,
        'grupo_id': grupo_uuid,
        'pode_gerenciar': _checar_gerenciar(request),
    })


@login_required
@require_POST
def retentar_ordem_servico(request, grupo_id):
    """Re-tenta abrir OS com slot/tecnico diferente. Mantem o grupo_tentativas_id."""
    if not _checar_gerenciar(request):
        return JsonResponse({'ok': False, 'error': 'Sem permissao para re-tentar.'}, status=403)

    try:
        grupo_uuid = uuid.UUID(str(grupo_id))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'grupo_id invalido'}, status=400)

    # Pega ultima tentativa do grupo pra reusar dados
    ultima = (
        OrdemServicoTentativa.objects
        .filter(grupo_tentativas_id=grupo_uuid)
        .order_by('-tentativa_numero')
        .select_related('integracao')
        .first()
    )
    if not ultima:
        return JsonResponse({'ok': False, 'error': 'Grupo nao encontrado'}, status=404)

    # Overrides do body (form-encoded ou JSON)
    if request.content_type and 'application/json' in request.content_type:
        import json as _json
        try:
            body = _json.loads(request.body or b'{}')
        except Exception:
            body = {}
    else:
        body = request.POST.dict()

    data_inicio = body.get('data_inicio_programado') or ultima.data_inicio_programado
    hora_inicio = body.get('hora_inicio_programado') or ultima.hora_inicio_programado
    data_termino = body.get('data_termino_programado') or ultima.data_termino_programado
    hora_termino = body.get('hora_termino_programado') or ultima.hora_termino_programado
    id_tecnico = body.get('id_tecnico') or ultima.id_tecnico

    integracao = ultima.integracao
    cfg = (integracao.configuracoes_extras or {}).get('os_matrix', {})

    nova = OrdemServicoTentativa(
        tenant=integracao.tenant,
        grupo_tentativas_id=grupo_uuid,
        tentativa_numero=ultima.tentativa_numero + 1,
        id_atendimento_hubsoft=ultima.id_atendimento_hubsoft,
        integracao=integracao,
        lead=ultima.lead,
        cliente_hubsoft=ultima.cliente_hubsoft,
        servico=ultima.servico,
        status='pendente',
        payload_enviado={
            'id_atendimento': ultima.id_atendimento_hubsoft,
            'data_inicio_programado': str(data_inicio) if data_inicio else None,
            'hora_inicio_programado': str(hora_inicio) if hora_inicio else None,
            'data_termino_programado': str(data_termino) if data_termino else None,
            'hora_termino_programado': str(hora_termino) if hora_termino else None,
            'id_tecnico': id_tecnico,
            '__source': 'retry_manual',
            '__usuario_id': request.user.id,
        },
        data_inicio_programado=data_inicio or None,
        hora_inicio_programado=hora_inicio or None,
        data_termino_programado=data_termino or None,
        hora_termino_programado=hora_termino or None,
        id_tecnico=int(id_tecnico) if id_tecnico else None,
        cidade=ultima.cidade,
        origem='retry_manual',
        usuario_retry=request.user,
    )

    t0 = time.monotonic()
    try:
        ordem = HubsoftService(integracao).abrir_os(
            id_atendimento=ultima.id_atendimento_hubsoft,
            id_agenda_ordem_servico=cfg.get('id_agenda_ordem_servico'),
            id_tipo_ordem_servico=cfg.get('id_tipo_os'),
            data_inicio_programado=str(data_inicio) if data_inicio else None,
            data_termino_programado=str(data_termino) if data_termino else None,
            hora_inicio_programado=str(hora_inicio) if hora_inicio else None,
            hora_termino_programado=str(hora_termino) if hora_termino else None,
            status=cfg.get('status_os') or 'pendente',
            tecnicos=[int(id_tecnico)] if id_tecnico else None,
            disponibilidade=None,
        )
        nova.status = 'sucesso'
        nova.resposta_hubsoft = ordem if isinstance(ordem, dict) else {'raw': str(ordem)[:2000]}
        if isinstance(ordem, dict):
            nova.id_ordem_servico_hubsoft = ordem.get('id_ordem_servico') or ordem.get('id')
        nova.duracao_ms = int((time.monotonic() - t0) * 1000)
        nova.save()
        return JsonResponse({'ok': True, 'tentativa_numero': nova.tentativa_numero, 'status': 'sucesso'})
    except HubsoftServiceError as e:
        msg = str(e)
        nova.status = 'falha'
        nova.motivo_falha_mensagem = msg[:2000]
        nova.motivo_falha_categoria = categorizar_falha_hubsoft(msg)
        nova.duracao_ms = int((time.monotonic() - t0) * 1000)
        nova.save()
        return JsonResponse({
            'ok': False, 'tentativa_numero': nova.tentativa_numero,
            'status': 'falha', 'msg': msg[:300],
            'categoria': nova.motivo_falha_categoria,
        }, status=200)
