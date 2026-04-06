"""
Provider genérico via Webhook — Para integrações N8N ou custom.
Envia mensagens via POST para uma URL configurada no canal.
"""
import logging
import requests

from . import register_provider
from .base import BaseProvider

logger = logging.getLogger(__name__)


@register_provider
class GenericWebhookProvider(BaseProvider):
    slug = 'webhook'
    display_name = 'Webhook Genérico'
    channel_type = 'whatsapp'

    def __init__(self, canal):
        # Não exige integracao FK (usa configuracao do canal)
        self.canal = canal
        self.integracao = canal.integracao  # pode ser None
        self._webhook_url = (canal.configuracao or {}).get('webhook_envio_url', '')

    def _post_webhook(self, payload):
        if not self._webhook_url:
            logger.warning("[Webhook] Nenhum webhook_envio_url configurado no canal %s", self.canal)
            return {'error': 'webhook_envio_url não configurado'}
        try:
            resp = requests.post(self._webhook_url, json=payload, timeout=10)
            return {'status_code': resp.status_code, 'ok': resp.status_code < 400}
        except Exception as e:
            logger.error("[Webhook] Erro: %s", e)
            raise

    def enviar_texto(self, telefone, mensagem):
        return self._post_webhook({'telefone': telefone, 'mensagem': mensagem, 'tipo': 'texto'})

    def enviar_imagem(self, telefone, url, legenda=''):
        return self._post_webhook({'telefone': telefone, 'imagem_url': url, 'legenda': legenda, 'tipo': 'imagem'})

    def enviar_documento(self, telefone, url, nome=''):
        return self._post_webhook({'telefone': telefone, 'documento_url': url, 'nome': nome, 'tipo': 'documento'})

    def enviar_audio(self, telefone, url):
        return self._post_webhook({'telefone': telefone, 'audio_url': url, 'tipo': 'audio'})

    def parse_webhook(self, body):
        # Webhook genérico não tem formato de recebimento padronizado
        # O N8N usa o endpoint separado em views_n8n.py
        return None
