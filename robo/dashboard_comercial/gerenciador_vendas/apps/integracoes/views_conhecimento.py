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
        from apps.comercial.leads.models import LeadProspecto
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


@csrf_exempt
@require_POST
@api_token_required
def registrar_erro_resposta(request):
    """POST /api/public/n8n/atendimento/registrar-erro-resposta/

    Telemetria de fricao no fluxo: bot perguntou X, cliente respondeu Y errado.
    Diferente de /conhecimento/registrar-pergunta/ (la o cliente pergunta livre).

    Body JSON:
      {
        "pergunta_bot": "qual seu CPF?",         # obrigatorio
        "resposta_cliente": "12345",             # obrigatorio
        "no_fluxo": "ColetaCPF",                 # opcional
        "canal": "whatsapp",                     # opcional
        "lead_id": 462,                          # opcional
        "conversa_id": 312                       # opcional
      }

    Resposta:
      {"status":"success","criada":true|false,"erro_id":N,"ocorrencias":N}
    """
    from apps.sistema.utils import _parse_json_request
    from apps.comercial.atendimento.services.motivo_erro_service import registrar_erro_resposta as svc

    data = _parse_json_request(request) or {}
    pb = (data.get('pergunta_bot') or '').strip()
    rc = (data.get('resposta_cliente') or '').strip()
    if not pb or not rc:
        return JsonResponse(
            {'status': 'error', 'msg': 'pergunta_bot e resposta_cliente sao obrigatorios'},
            status=400,
        )

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'status': 'error', 'msg': 'tenant nao resolvido'}, status=401)

    lead = None
    if data.get('lead_id'):
        from apps.comercial.leads.models import LeadProspecto
        lead = LeadProspecto.all_tenants.filter(tenant=tenant, id=data['lead_id']).first()
    conversa = None
    if data.get('conversa_id'):
        from apps.inbox.models import Conversa
        conversa = Conversa.all_tenants.filter(tenant=tenant, id=data['conversa_id']).first()

    try:
        obj, criada = svc(
            tenant=tenant,
            pergunta_bot=pb, resposta_cliente=rc,
            no_fluxo=(data.get('no_fluxo') or '').strip(),
            canal=(data.get('canal') or '').strip(),
            lead=lead, conversa=conversa,
        )
    except Exception as e:
        logger.exception('Erro ao registrar erro de resposta')
        return JsonResponse({'status': 'error', 'msg': str(e)[:300]}, status=400)

    if not obj:
        return JsonResponse({'status': 'error', 'msg': 'payload invalido'}, status=400)

    return JsonResponse({
        'status': 'success',
        'criada': criada,
        'erro_id': obj.id,
        'ocorrencias': obj.ocorrencias,
    })
