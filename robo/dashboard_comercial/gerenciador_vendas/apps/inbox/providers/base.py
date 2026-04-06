"""
Base class para provedores de mensageria.
Cada provider implementa envio e parsing de webhook para seu formato específico.
"""
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Abstract base class para todos os provedores de mensageria."""

    slug = ''           # ex: 'uazapi', 'evolution', 'twilio'
    display_name = ''   # ex: 'Uazapi (WhatsApp)'
    channel_type = ''   # ex: 'whatsapp', 'sms'

    def __init__(self, canal):
        """
        Inicializa com um CanalInbox.
        O canal carrega a IntegracaoAPI com credenciais.
        """
        self.canal = canal
        self.integracao = canal.integracao
        if not self.integracao:
            raise ValueError(f"Canal '{canal}' não tem integração vinculada.")

    # ── Envio de mensagens ──

    @abstractmethod
    def enviar_texto(self, telefone, mensagem):
        """Envia mensagem de texto. Retorna dict com resposta do provider."""

    @abstractmethod
    def enviar_imagem(self, telefone, url, legenda=''):
        """Envia imagem com legenda opcional."""

    @abstractmethod
    def enviar_documento(self, telefone, url, nome=''):
        """Envia documento/arquivo."""

    @abstractmethod
    def enviar_audio(self, telefone, url):
        """Envia áudio."""

    def enviar_mensagem(self, conversa, mensagem):
        """
        Roteia uma Mensagem para o método de envio correto baseado no tipo_conteudo.
        Subclasses podem sobrescrever para tipos customizados.
        """
        telefone = conversa.contato_telefone

        if mensagem.tipo_conteudo == 'texto':
            return self.enviar_texto(telefone, mensagem.conteudo)
        elif mensagem.tipo_conteudo == 'imagem' and mensagem.arquivo_url:
            return self.enviar_imagem(telefone, mensagem.arquivo_url, mensagem.conteudo)
        elif mensagem.tipo_conteudo in ('arquivo', 'documento') and mensagem.arquivo_url:
            return self.enviar_documento(telefone, mensagem.arquivo_url, mensagem.arquivo_nome)
        elif mensagem.tipo_conteudo == 'audio' and mensagem.arquivo_url:
            return self.enviar_audio(telefone, mensagem.arquivo_url)
        else:
            # Fallback: envia como texto
            return self.enviar_texto(telefone, mensagem.conteudo)

    # ── Recebimento (webhook parsing) ──

    @abstractmethod
    def parse_webhook(self, body):
        """
        Parseia payload do webhook em formato normalizado.

        Retorna dict:
        {
            'telefone': '5589...',
            'nome': 'Nome do Contato',
            'conteudo': 'texto da mensagem',
            'tipo_conteudo': 'texto|imagem|audio|arquivo|video|localizacao',
            'identificador_externo': 'msg-id-do-provider',
            'arquivo_url': '',
            'arquivo_nome': '',
            'metadata': {},
            'is_status_update': False,
            'status_data': None,
        }

        Retorna None para ignorar o evento.
        """

    # ── Helpers ──

    def extrair_msg_id(self, result):
        """Extrai message ID da resposta de envio. Sobrescrever por provider."""
        return ''
