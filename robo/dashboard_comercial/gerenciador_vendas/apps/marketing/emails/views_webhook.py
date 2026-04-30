"""
Webhook publico do Resend.

Endpoint: /api/public/resend/webhook/
Sem auth de usuario — valida via assinatura HMAC.

Eventos do Resend:
  email.sent
  email.delivered
  email.delivery_delayed
  email.complained     (marcado como spam)
  email.bounced
  email.opened
  email.clicked

Ao receber, atualiza o EnvioEmail correspondente via resend_message_id.
"""
import json
import logging

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import EnvioEmail
from .services import resend_service

logger = logging.getLogger(__name__)


EVENTOS_MAP = {
    'email.sent':              ('enviado',    'enviado_em'),
    'email.delivered':         ('entregue',   'entregue_em'),
    'email.opened':            ('aberto',     'aberto_em'),
    'email.clicked':           ('clicado',    'clicado_em'),
    'email.bounced':           ('bounce',     None),
    'email.complained':        ('complained', None),
    'email.delivery_delayed':  (None,         None),  # nao muda status
}


@csrf_exempt
@require_POST
def resend_webhook(request):
    payload_bytes = request.body
    signature = request.META.get('HTTP_SVIX_SIGNATURE', '') or request.META.get('HTTP_RESEND_SIGNATURE', '')

    if not resend_service.verify_webhook_signature(payload_bytes, signature):
        logger.warning('Webhook Resend com assinatura invalida')
        return HttpResponse(status=401)

    try:
        evento = json.loads(payload_bytes.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning('Webhook Resend payload invalido: %s', e)
        return HttpResponse(status=400)

    tipo = evento.get('type', '')
    data = evento.get('data', {})
    msg_id = data.get('email_id') or data.get('id')

    if not msg_id:
        return JsonResponse({'ignored': 'sem email_id'}, status=200)

    envio = EnvioEmail.all_tenants.filter(resend_message_id=msg_id).first()
    if not envio:
        # Pode ser de outro tenant ou email enviado fora do sistema; ignora
        return JsonResponse({'ignored': 'envio nao encontrado'}, status=200)

    # Verifica flag do dominio
    if envio.remetente:
        flags = envio.remetente.dominio
        if tipo == 'email.bounced' and not flags.capturar_bounces:
            return JsonResponse({'ignored': 'bounces desabilitados'}, status=200)
        if tipo == 'email.complained' and not flags.capturar_complaints:
            return JsonResponse({'ignored': 'complaints desabilitados'}, status=200)

    novo_status, campo_data = EVENTOS_MAP.get(tipo, (None, None))

    if novo_status:
        envio.status = novo_status
    if campo_data and not getattr(envio, campo_data, None):
        setattr(envio, campo_data, timezone.now())

    if tipo == 'email.bounced':
        envio.bounce_type = data.get('bounce', {}).get('type', 'undetermined')[:50]
    elif tipo == 'email.complained':
        envio.complaint_type = data.get('type', 'spam')[:50]

    envio.save()

    # Auto-remover lista se flag ativa
    if envio.remetente and envio.remetente.dominio.auto_remover_lista:
        if tipo in ('email.bounced', 'email.complained') and envio.lead_id:
            try:
                from apps.comercial.leads.models import LeadProspecto
                lead = LeadProspecto.all_tenants.filter(pk=envio.lead_id).first()
                if lead and hasattr(lead, 'aceita_emails'):
                    lead.aceita_emails = False
                    lead.save(update_fields=['aceita_emails'])
            except Exception as e:
                logger.warning('Falha ao auto-remover lead da lista: %s', e)

    return JsonResponse({'ok': True, 'status': envio.status}, status=200)
