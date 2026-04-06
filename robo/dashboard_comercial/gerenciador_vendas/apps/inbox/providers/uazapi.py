"""
Provider Uazapi — WhatsApp via Uazapi API.
"""
from . import register_provider
from .base import BaseProvider


def _extrair_telefone(jid):
    """Extrai número do JID WhatsApp (5589999999999@s.whatsapp.net → 5589999999999)."""
    if not jid:
        return ''
    return jid.split('@')[0].replace('+', '')


def _extrair_telefone_formatado(phone_str):
    """Extrai número de telefone formatado (+55 53 8152-1653 → 5553981521653)."""
    import re
    if not phone_str:
        return ''
    return re.sub(r'\D', '', phone_str)


def _detectar_tipo_conteudo(message_data):
    """Detecta tipo de conteúdo do payload Uazapi."""
    if not message_data:
        return 'texto', '', '', ''

    if 'conversation' in message_data:
        return 'texto', message_data['conversation'], '', ''
    if 'extendedTextMessage' in message_data:
        return 'texto', message_data['extendedTextMessage'].get('text', ''), '', ''
    if 'imageMessage' in message_data:
        return 'imagem', message_data['imageMessage'].get('caption', ''), message_data['imageMessage'].get('url', ''), ''
    if 'documentMessage' in message_data:
        return 'arquivo', message_data['documentMessage'].get('caption', ''), message_data['documentMessage'].get('url', ''), message_data['documentMessage'].get('fileName', 'documento')
    if 'audioMessage' in message_data:
        return 'audio', '', message_data['audioMessage'].get('url', ''), 'audio'
    if 'videoMessage' in message_data:
        return 'video', message_data['videoMessage'].get('caption', ''), message_data['videoMessage'].get('url', ''), ''
    if 'stickerMessage' in message_data:
        return 'imagem', '[Sticker]', '', ''
    if 'locationMessage' in message_data:
        lat = message_data['locationMessage'].get('degreesLatitude', '')
        lng = message_data['locationMessage'].get('degreesLongitude', '')
        return 'localizacao', f'Localização: {lat}, {lng}', '', ''
    if 'contactMessage' in message_data:
        nome = message_data['contactMessage'].get('displayName', 'Contato')
        return 'texto', f'[Contato compartilhado: {nome}]', '', ''

    return 'texto', '[Mensagem não suportada]', '', ''


@register_provider
class UazapiProvider(BaseProvider):
    slug = 'uazapi'
    display_name = 'Uazapi (WhatsApp)'
    channel_type = 'whatsapp'

    def __init__(self, canal):
        super().__init__(canal)
        from apps.integracoes.services.uazapi import UazapiService
        self._service = UazapiService(integracao=self.integracao)

    # ── Envio ──

    def enviar_texto(self, telefone, mensagem):
        return self._service.enviar_texto(telefone, mensagem)

    def enviar_imagem(self, telefone, url, legenda=''):
        return self._service.enviar_imagem(telefone, url, legenda)

    def enviar_documento(self, telefone, url, nome=''):
        return self._service.enviar_documento(telefone, url, nome)

    def enviar_audio(self, telefone, url):
        return self._service.enviar_audio(telefone, url)

    def extrair_msg_id(self, result):
        if isinstance(result, dict):
            return result.get('key', {}).get('id', '')
        return ''

    # ── Métodos extras Uazapi ──

    def enviar_vcard(self, telefone, nome_contato, telefone_contato):
        return self._service._post('/send/contact', {
            'phone': self._service._normalizar_telefone(telefone),
            'contactName': nome_contato,
            'contactPhone': self._service._normalizar_telefone(telefone_contato),
        })

    def enviar_localizacao(self, telefone, latitude, longitude, nome='', endereco=''):
        return self._service._post('/send/location', {
            'phone': self._service._normalizar_telefone(telefone),
            'lat': str(latitude),
            'lng': str(longitude),
            'name': nome,
            'address': endereco,
        })

    def enviar_menu_interativo(self, telefone, titulo, descricao, botoes=None, secoes=None):
        payload = {
            'phone': self._service._normalizar_telefone(telefone),
            'title': titulo,
            'description': descricao,
        }
        if botoes:
            payload['buttons'] = botoes
        if secoes:
            payload['sections'] = secoes
        return self._service._post('/send/interactive', payload)

    def enviar_carrossel(self, telefone, cards):
        return self._service._post('/send/carousel', {
            'phone': self._service._normalizar_telefone(telefone),
            'cards': cards,
        })

    def enviar_botao_pix(self, telefone, chave_pix, valor, descricao=''):
        return self._service._post('/send/pix', {
            'phone': self._service._normalizar_telefone(telefone),
            'key': chave_pix,
            'amount': valor,
            'description': descricao,
        })

    def enviar_presenca(self, telefone, tipo='composing'):
        return self._service._post('/send/presence', {
            'phone': self._service._normalizar_telefone(telefone),
            'type': tipo,
        })

    def solicitar_localizacao(self, telefone, mensagem='Compartilhe sua localização'):
        return self._service._post('/send/requestLocation', {
            'phone': self._service._normalizar_telefone(telefone),
            'message': mensagem,
        })

    # ── Webhook parsing ──

    def parse_webhook(self, body):
        """
        Parseia webhook do Uazapi. Suporta dois formatos:
        - Formato Uazapi real: {EventType, message: {text, chatid, fromMe, ...}, chat: {phone, ...}}
        - Formato Baileys/legacy: {event, data: {key: {remoteJid, ...}, message: {conversation, ...}}}
        """
        # Detectar formato pelo campo EventType (formato Uazapi real)
        event_type = body.get('EventType', '')
        if event_type:
            return self._parse_uazapi_format(body, event_type)

        # Formato Baileys/legacy
        event = body.get('event', '')
        if event:
            return self._parse_baileys_format(body, event)

        # Tentar detectar pelo conteúdo
        if 'message' in body and 'chat' in body:
            return self._parse_uazapi_format(body, 'messages')

        return None

    def _parse_uazapi_format(self, body, event_type):
        """Formato real do Uazapi: EventType, message.text, chat.phone, etc."""

        # Ignorar eventos que não são mensagem
        if event_type not in ('messages', 'message', ''):
            return None

        message = body.get('message', {})
        chat = body.get('chat', {})

        # Ignorar mensagens enviadas por nós
        if message.get('fromMe', False):
            return None

        # Ignorar grupos
        if chat.get('wa_isGroup', False):
            return None

        # Extrair telefone do chat
        phone_raw = chat.get('phone', '')
        telefone = _extrair_telefone_formatado(phone_raw)
        if not telefone:
            chatid = message.get('chatid', '') or chat.get('wa_chatid', '')
            telefone = _extrair_telefone(chatid)
        if not telefone:
            return None

        # Conteúdo da mensagem
        conteudo = message.get('text', '') or message.get('content', '')
        msg_type = message.get('messageType', '').lower() or message.get('type', '').lower()
        arquivo_url = ''
        arquivo_nome = ''
        tipo_conteudo = 'texto'

        if msg_type in ('image', 'imageMessage'):
            tipo_conteudo = 'imagem'
            arquivo_url = message.get('mediaUrl', '') or message.get('media', '')
        elif msg_type in ('document', 'documentMessage'):
            tipo_conteudo = 'arquivo'
            arquivo_url = message.get('mediaUrl', '') or message.get('media', '')
            arquivo_nome = message.get('fileName', 'documento')
        elif msg_type in ('audio', 'audioMessage', 'ptt'):
            tipo_conteudo = 'audio'
            arquivo_url = message.get('mediaUrl', '') or message.get('media', '')
        elif msg_type in ('video', 'videoMessage'):
            tipo_conteudo = 'video'
            arquivo_url = message.get('mediaUrl', '') or message.get('media', '')
        elif msg_type in ('location', 'locationMessage'):
            tipo_conteudo = 'localizacao'
        elif msg_type in ('vcard', 'contactMessage', 'contact'):
            conteudo = f"[Contato: {message.get('vcardName', '')}]"
        elif msg_type in ('sticker', 'stickerMessage'):
            tipo_conteudo = 'imagem'
            conteudo = '[Sticker]'

        if not conteudo and not arquivo_url:
            return None

        # Nome do contato
        nome = message.get('senderName', '') or chat.get('wa_contactName', '') or chat.get('name', '')

        return {
            'telefone': telefone,
            'nome': nome,
            'conteudo': conteudo,
            'tipo_conteudo': tipo_conteudo,
            'identificador_externo': message.get('messageid', '') or message.get('id', ''),
            'arquivo_url': arquivo_url,
            'arquivo_nome': arquivo_nome,
            'metadata': {
                'uazapi_event': body.get('EventType', ''),
                'timestamp': message.get('messageTimestamp', ''),
                'instance': body.get('instanceName', ''),
            },
            'is_status_update': False,
        }

    def _parse_baileys_format(self, body, event):
        """Formato Baileys/legacy: event, data.key.remoteJid, etc."""

        # Status updates
        if event in ('messages.update', 'message.update'):
            return {'is_status_update': True, 'status_data': body.get('data', body)}

        # Filtrar eventos que não são mensagem
        eventos_mensagem = ['messages.upsert', 'messages', 'message', 'message.new']
        if event not in eventos_mensagem:
            return None

        data = body.get('data', body)
        key = data.get('key', {})
        if key.get('fromMe', False):
            return None

        remote_jid = key.get('remoteJid', '')
        if '@g.us' in remote_jid or '@broadcast' in remote_jid:
            return None

        telefone = _extrair_telefone(remote_jid)
        if not telefone:
            return None

        message_data = data.get('message', {})
        tipo, conteudo, arquivo_url, arquivo_nome = _detectar_tipo_conteudo(message_data)

        if not conteudo and not arquivo_url:
            return None

        return {
            'telefone': telefone,
            'nome': data.get('pushName', ''),
            'conteudo': conteudo,
            'tipo_conteudo': tipo,
            'identificador_externo': key.get('id', ''),
            'arquivo_url': arquivo_url,
            'arquivo_nome': arquivo_nome,
            'metadata': {'event': event, 'timestamp': data.get('messageTimestamp', '')},
            'is_status_update': False,
        }
