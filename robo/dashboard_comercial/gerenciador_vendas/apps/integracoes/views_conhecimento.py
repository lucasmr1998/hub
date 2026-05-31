"""Endpoints publicos /api/public/n8n/conhecimento/* — base de conhecimento.

Permitem que bots externos (Matrix, N8N agente LLM) registrem perguntas sem
resposta e (futuramente) busquem na base de conhecimento. Autenticam por
Bearer token via api_token_required → request.tenant.
"""
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.sistema.decorators import api_token_required

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
@api_token_required
def registrar_pergunta(request):
    """POST /api/public/n8n/conhecimento/registrar-pergunta/

    Body JSON:
      {
        "pergunta": "qual o valor do plano 500MB?",   # obrigatorio
        "lead_id": 462,        # opcional
        "conversa_id": 312     # opcional
      }

    Resposta:
      {"status": "success",
       "criada": true|false,         # true=nova, false=incrementou ocorrencias
       "pergunta_id": 28,
       "ocorrencias": 3}
    """
    from apps.sistema.utils import _parse_json_request
    from apps.suporte.services import registrar_pergunta_sem_resposta

    data = _parse_json_request(request) or {}
    pergunta = (data.get('pergunta') or '').strip()
    if not pergunta or len(pergunta) < 3:
        return JsonResponse(
            {'status': 'error', 'msg': 'pergunta obrigatoria (min 3 chars)'},
            status=400,
        )

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'status': 'error', 'msg': 'tenant nao resolvido'}, status=401)

    lead = None
    if data.get('lead_id'):
        from apps.leads.models import LeadProspecto
        lead = LeadProspecto.all_tenants.filter(tenant=tenant, id=data['lead_id']).first()

    conversa = None
    if data.get('conversa_id'):
        from apps.inbox.models import Conversa
        conversa = Conversa.all_tenants.filter(tenant=tenant, id=data['conversa_id']).first()

    try:
        obj, criada = registrar_pergunta_sem_resposta(
            tenant=tenant, pergunta=pergunta, lead=lead, conversa=conversa,
        )
    except Exception as e:
        logger.exception('Erro ao registrar pergunta sem resposta')
        return JsonResponse({'status': 'error', 'msg': str(e)[:300]}, status=400)

    if not obj:
        return JsonResponse(
            {'status': 'error', 'msg': 'pergunta invalida'}, status=400,
        )

    return JsonResponse({
        'status': 'success',
        'criada': criada,
        'pergunta_id': obj.id,
        'ocorrencias': obj.ocorrencias,
    })
