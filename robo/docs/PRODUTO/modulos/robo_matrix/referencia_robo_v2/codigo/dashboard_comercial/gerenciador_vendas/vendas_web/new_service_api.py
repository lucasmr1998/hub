"""Endpoints HTTP do fluxo de contratação de novo serviço.

Espelha o estilo de `views.py` (sem DRF, JSON puro, `@csrf_exempt`),
mantendo o NewService como entidade isolada — a IA (engine.py) chama
estes endpoints quando o cliente está no fluxo de "Contratar novo serviço".

Sem integração Hubsoft por enquanto: tudo registra na nossa base.
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime

from django.db import models
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import LeadProspecto, NewService, ImagemNewService
from .views import _apply_updates, _parse_json_request, _serialize_instance

logger = logging.getLogger(__name__)


def _serialize_new_service(ns: NewService) -> dict:
    """Versão enxuta — só os campos que a IA precisa pra rotear o fluxo."""
    data = _serialize_instance(ns)
    # Garante campos extras úteis pra IA
    data['lead_id'] = ns.lead_id
    data['status'] = ns.status
    if ns.criado_em:
        data['criado_em'] = ns.criado_em.isoformat()
    if ns.finalizado_em:
        data['finalizado_em'] = ns.finalizado_em.isoformat()
    return data


# ──────────────────────────────────────────────────────────────────────
#  CRIAR — chamado quando cliente escolhe "1) Contratar novo serviço"
# ──────────────────────────────────────────────────────────────────────
@csrf_exempt
def criar_new_service_api(request):
    """POST { lead_id } → cancela em-coleta antigos e cria um NewService NOVO.

    Política: cada vez que o cliente escolhe "Contratar novo serviço" do menu,
    a coleta começa do zero. NewServices em coleta anteriores são marcados
    como 'cancelado' (preservados pra auditoria, mas fora de cena).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    lead_id = data.get('lead_id')
    if not lead_id:
        return JsonResponse({'error': 'Campo obrigatório: lead_id'}, status=400)

    try:
        lead = LeadProspecto.objects.get(pk=lead_id)
    except LeadProspecto.DoesNotExist:
        return JsonResponse({'error': f'Lead #{lead_id} não encontrado'}, status=404)

    # Cancela qualquer em-coleta antigo (cliente reescolheu/abandonou)
    cancelados = NewService.objects.filter(lead=lead, status='em_coleta').update(
        status='cancelado',
        observacoes=models.functions.Concat(
            'observacoes',
            models.Value('\n[auto] Cancelado: cliente iniciou novo fluxo.'),
        ),
    )
    ns = NewService.objects.create(lead=lead, status='em_coleta')

    return JsonResponse({
        'success': True,
        'criado': True,
        'cancelados_antigos': cancelados,
        'new_service': _serialize_new_service(ns),
    }, status=201)


# ──────────────────────────────────────────────────────────────────────
#  ATUALIZAR — escreve campos coletados pela IA
# ──────────────────────────────────────────────────────────────────────
@csrf_exempt
def atualizar_new_service_api(request):
    """POST { id, ...campos } — escreve campos no NewService.

    Mesma semântica do `atualizar_lead_api` mas sem o termo_busca (sempre por id).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    new_service_id = data.get('id') or data.get('new_service_id')
    if not new_service_id:
        return JsonResponse({'error': 'Campo obrigatório: id'}, status=400)

    try:
        ns = NewService.objects.get(pk=new_service_id)
    except NewService.DoesNotExist:
        return JsonResponse({'error': f'NewService #{new_service_id} não encontrado'}, status=404)

    updates = {
        k: v for k, v in data.items()
        if k not in ('id', 'new_service_id')
    }
    if not updates:
        return JsonResponse({'error': 'Nenhum campo para atualizar'}, status=400)

    try:
        _apply_updates(ns, updates)
        return JsonResponse({
            'success': True,
            'new_service': _serialize_new_service(ns),
        })
    except Exception as e:
        logger.exception('Erro atualizar NewService #%s: %s', new_service_id, e)
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()[-500:],
        }, status=400)


# ──────────────────────────────────────────────────────────────────────
#  OBTER — busca por id ou (lead_id + status)
# ──────────────────────────────────────────────────────────────────────
@csrf_exempt
def obter_new_service_api(request):
    """GET ?id=N → retorna NewService #N
       GET ?lead_id=N&status=em_coleta → retorna o NewService em coleta do lead
    """
    nid = request.GET.get('id')
    lead_id = request.GET.get('lead_id')
    status = request.GET.get('status', 'em_coleta')

    qs = NewService.objects.all()
    if nid:
        qs = qs.filter(pk=nid)
    elif lead_id:
        qs = qs.filter(lead_id=lead_id, status=status)
    else:
        return JsonResponse({'error': 'Informe id ou lead_id'}, status=400)

    ns = qs.first()
    if not ns:
        return JsonResponse({'found': False, 'new_service': None})

    return JsonResponse({
        'found': True,
        'new_service': _serialize_new_service(ns),
    })


# ──────────────────────────────────────────────────────────────────────
#  REGISTRAR IMAGEM — chamada quando IA aprovou foto de doc
# ──────────────────────────────────────────────────────────────────────
@csrf_exempt
def registrar_imagem_new_service_api(request):
    """POST { new_service_id, link_url, descricao, status_validacao?, observacao_validacao? }"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    new_service_id = data.get('new_service_id')
    if not new_service_id:
        return JsonResponse({'error': 'Campo obrigatório: new_service_id'}, status=400)

    try:
        ns = NewService.objects.get(pk=new_service_id)
    except NewService.DoesNotExist:
        return JsonResponse({'error': f'NewService #{new_service_id} não encontrado'}, status=404)

    link_url = (data.get('link_url') or '').strip()
    if not link_url:
        return JsonResponse({'error': 'Campo obrigatório: link_url'}, status=400)

    img = ImagemNewService.objects.create(
        new_service=ns,
        link_url=link_url,
        descricao=data.get('descricao', ''),
        status_validacao=data.get('status_validacao') or ImagemNewService.STATUS_PENDENTE,
        observacao_validacao=data.get('observacao_validacao', ''),
    )
    return JsonResponse({
        'success': True,
        'imagem': {
            'id': img.id,
            'new_service_id': ns.id,
            'link_url': img.link_url,
            'descricao': img.descricao,
            'status_validacao': img.status_validacao,
            'data_criacao': img.data_criacao.isoformat(),
        },
    }, status=201)


# ──────────────────────────────────────────────────────────────────────
#  FINALIZAR — encerra a coleta (sem integração Hubsoft)
# ──────────────────────────────────────────────────────────────────────
@csrf_exempt
def finalizar_new_service_api(request):
    """POST { id, observacoes? } → status='finalizado', finalizado_em=now.

    Conversa com cliente concluída (todos os campos coletados + docs +
    turno + data). Marca como 'finalizado' — o signal `post_save` de
    NewService (em `vendas_web/signals.py`) dispara automaticamente a
    abertura de Atendimento + OS no Matrix em thread daemon.

    O bot recebe a confirmação imediatamente; o sync com Matrix acontece
    em background. Se falhar, o worker periódico
    `processar_newservice_finalizados` reprocessa.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    nid = data.get('id') or data.get('new_service_id')
    if not nid:
        return JsonResponse({'error': 'Campo obrigatório: id'}, status=400)

    try:
        ns = NewService.objects.get(pk=nid)
    except NewService.DoesNotExist:
        return JsonResponse({'error': f'NewService #{nid} não encontrado'}, status=404)

    ns.status = 'finalizado'
    ns.finalizado_em = timezone.now()
    obs = (data.get('observacoes') or '').strip()
    if obs:
        ns.observacoes = (ns.observacoes + '\n' + obs).strip() if ns.observacoes else obs
    # save dispara post_save → signal abre Atendimento+OS em background
    ns.save(update_fields=['status', 'finalizado_em', 'observacoes', 'atualizado_em'])

    return JsonResponse({
        'success': True,
        'new_service': _serialize_new_service(ns),
        'sync_matrix_disparado': True,
    })
