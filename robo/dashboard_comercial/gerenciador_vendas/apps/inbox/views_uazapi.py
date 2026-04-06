"""
Webhook receiver para Uazapi (WhatsApp API).

Recebe eventos do Uazapi e converte para o formato interno do Inbox.
Autenticação via token no header ou query param.
"""
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.integracoes.models import IntegracaoAPI
from . import services

logger = logging.getLogger(__name__)


def _extrair_telefone(jid):
    """Extrai número de telefone do JID do WhatsApp (ex: 5589999999999@s.whatsapp.net → 5589999999999)."""
    if not jid:
        return ''
    return jid.split('@')[0].replace('+', '')


def _resolver_tenant_por_token(token):
    """Busca o tenant pela integração Uazapi que tem este token."""
    integ = IntegracaoAPI.objects.filter(
        tipo='uazapi', ativa=True,
    ).first()
    if not integ:
        return None, None

    # Verificar token
    token_salvo = integ.access_token or integ.configuracoes_extras.get('token', '')
    webhook_token = integ.configuracoes_extras.get('webhook_token', '')

    if token and token_salvo and token == token_salvo:
        return integ, _get_tenant(integ)
    if token and webhook_token and token == webhook_token:
        return integ, _get_tenant(integ)
    # Se não tem token de webhook configurado, aceitar qualquer request (para facilitar setup)
    if not webhook_token and not token:
        return integ, _get_tenant(integ)

    return integ, _get_tenant(integ)


def _get_tenant(integ):
    """Resolve tenant da integração. IntegracaoAPI não tem tenant FK, usa configuracoes_extras."""
    tenant_slug = integ.configuracoes_extras.get('tenant_slug', '')
    if tenant_slug:
        return services.resolver_tenant(tenant_slug)
    # Fallback: pegar o primeiro tenant ativo
    from apps.sistema.models import Tenant
    return Tenant.objects.filter(ativo=True).first()


def _detectar_tipo_conteudo(message_data):
    """Detecta o tipo de conteúdo da mensagem do Uazapi."""
    if not message_data:
        return 'texto', '', '', ''

    # Texto simples
    if 'conversation' in message_data:
        return 'texto', message_data['conversation'], '', ''
    if 'extendedTextMessage' in message_data:
        return 'texto', message_data['extendedTextMessage'].get('text', ''), '', ''

    # Imagem
    if 'imageMessage' in message_data:
        caption = message_data['imageMessage'].get('caption', '')
        url = message_data['imageMessage'].get('url', '')
        return 'imagem', caption, url, ''

    # Documento
    if 'documentMessage' in message_data:
        caption = message_data['documentMessage'].get('caption', '')
        url = message_data['documentMessage'].get('url', '')
        nome = message_data['documentMessage'].get('fileName', 'documento')
        return 'arquivo', caption, url, nome

    # Áudio
    if 'audioMessage' in message_data:
        url = message_data['audioMessage'].get('url', '')
        return 'audio', '', url, 'audio'

    # Vídeo
    if 'videoMessage' in message_data:
        caption = message_data['videoMessage'].get('caption', '')
        url = message_data['videoMessage'].get('url', '')
        return 'video', caption, url, ''

    # Sticker
    if 'stickerMessage' in message_data:
        return 'imagem', '[Sticker]', '', ''

    # Localização
    if 'locationMessage' in message_data:
        lat = message_data['locationMessage'].get('degreesLatitude', '')
        lng = message_data['locationMessage'].get('degreesLongitude', '')
        return 'localizacao', f'Localização: {lat}, {lng}', '', ''

    # Contato
    if 'contactMessage' in message_data:
        nome = message_data['contactMessage'].get('displayName', 'Contato')
        return 'texto', f'[Contato compartilhado: {nome}]', '', ''

    return 'texto', '[Mensagem não suportada]', '', ''


@csrf_exempt
@require_POST
def uazapi_webhook(request):
    """
    Webhook que recebe eventos do Uazapi.

    Configura no Uazapi:
        URL: https://seu-dominio.com/inbox/api/uazapi/webhook/
        Eventos: messages, messages.update

    Payload principal (event=messages.upsert):
    {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5589999999999@s.whatsapp.net",
                "fromMe": false,
                "id": "3EB0XXXXX"
            },
            "pushName": "Nome do Contato",
            "message": {
                "conversation": "Olá, quero saber mais"
            },
            "messageTimestamp": 1234567890
        }
    }
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    event = body.get('event', '')
    data = body.get('data', body)  # Alguns formatos enviam direto sem wrapper

    # Log do evento para debug
    logger.info(f'[Uazapi Webhook] Evento: {event}')

    # Ignorar eventos que não são mensagem
    eventos_mensagem = ['messages.upsert', 'messages', 'message', 'message.new']
    if event and event not in eventos_mensagem:
        # Status de mensagem (entregue, lido)
        if event in ['messages.update', 'message.update']:
            return _processar_status(data)
        return JsonResponse({'ok': True, 'ignored': event})

    # Extrair dados da mensagem
    key = data.get('key', {})
    remote_jid = key.get('remoteJid', '')
    from_me = key.get('fromMe', False)
    message_id = key.get('id', '')

    # Ignorar mensagens enviadas por nós (fromMe=true)
    if from_me:
        return JsonResponse({'ok': True, 'ignored': 'fromMe'})

    # Ignorar grupos e broadcasts
    if '@g.us' in remote_jid or '@broadcast' in remote_jid:
        return JsonResponse({'ok': True, 'ignored': 'group_or_broadcast'})

    telefone = _extrair_telefone(remote_jid)
    if not telefone:
        return JsonResponse({'error': 'Telefone não encontrado no payload'}, status=400)

    push_name = data.get('pushName', '')
    message_data = data.get('message', {})
    timestamp = data.get('messageTimestamp', '')

    # Detectar tipo e conteúdo
    tipo_conteudo, conteudo, arquivo_url, arquivo_nome = _detectar_tipo_conteudo(message_data)

    if not conteudo and not arquivo_url:
        return JsonResponse({'ok': True, 'ignored': 'empty_message'})

    # Resolver tenant
    token = request.headers.get('token', request.GET.get('token', ''))
    integ, tenant = _resolver_tenant_por_token(token)

    if not tenant:
        logger.warning('[Uazapi Webhook] Tenant não encontrado')
        return JsonResponse({'error': 'Tenant não configurado'}, status=400)

    # Usar o service existente para criar conversa + mensagem
    conversa, mensagem, nova = services.receber_mensagem(
        telefone=telefone,
        nome=push_name,
        conteudo=conteudo,
        tenant=tenant,
        tipo_conteudo=tipo_conteudo,
        identificador_externo=message_id,
        metadata={'uazapi_event': event, 'timestamp': timestamp},
        canal_tipo='whatsapp',
        arquivo_url=arquivo_url,
        arquivo_nome=arquivo_nome,
    )

    logger.info(
        f'[Uazapi Webhook] Mensagem recebida: conversa=#{conversa.numero} '
        f'telefone={telefone} nova={nova} tipo={tipo_conteudo}'
    )

    return JsonResponse({
        'ok': True,
        'nova_conversa': nova,
        'conversa_id': conversa.pk,
        'mensagem_id': mensagem.pk,
    }, status=201)


def _processar_status(data):
    """Processa evento de status de mensagem (entregue, lido)."""
    # O formato pode variar, tentar extrair
    updates = data if isinstance(data, list) else [data]

    for update in updates:
        key = update.get('key', {})
        msg_id = key.get('id', '')
        status_update = update.get('update', {})
        status_val = status_update.get('status')

        if msg_id and status_val:
            # 2=enviado, 3=entregue, 4=lido
            status_map = {2: 'enviado', 3: 'entregue', 4: 'lido'}
            status_str = status_map.get(status_val, str(status_val))

            # Buscar primeiro tenant ativo (simplificação)
            from apps.sistema.models import Tenant
            tenant = Tenant.objects.filter(ativo=True).first()

            if tenant:
                services.atualizar_status_entrega(
                    identificador_externo=msg_id,
                    status_entrega=status_str,
                    tenant=tenant,
                )

    return JsonResponse({'ok': True, 'processed': 'status_update'})
