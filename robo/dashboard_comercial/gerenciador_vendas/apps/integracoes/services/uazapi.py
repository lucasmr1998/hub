"""
Service para comunicação com a API do Uazapi.
Envio de mensagens de texto, imagem, documento e áudio.
"""
import logging

import requests

from apps.integracoes.models import IntegracaoAPI

logger = logging.getLogger(__name__)


class UazapiServiceError(Exception):
    pass


class UazapiService:
    """Encapsula a comunicação com a API do Uazapi."""

    def __init__(self, integracao: IntegracaoAPI = None):
        if integracao is None:
            integracao = IntegracaoAPI.objects.filter(tipo='uazapi', ativa=True).first()
        if not integracao:
            raise UazapiServiceError('Nenhuma integração Uazapi ativa encontrada.')
        if integracao.tipo != 'uazapi':
            raise UazapiServiceError(f'Integração "{integracao.nome}" não é do tipo uazapi.')

        self.integracao = integracao
        self.base_url = integracao.base_url.rstrip('/')
        self.token = integracao.configuracoes_extras.get('token', '') or integracao.access_token or ''

    def _headers(self):
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'token': self.token,
        }

    def _post(self, endpoint, payload):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=15)
            data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {'raw': resp.text[:500]}

            if resp.status_code not in (200, 201):
                logger.warning(f'[Uazapi] {endpoint} retornou {resp.status_code}: {data}')
                raise UazapiServiceError(f'HTTP {resp.status_code}: {data}')

            return data
        except requests.RequestException as e:
            logger.error(f'[Uazapi] Erro de conexão em {endpoint}: {e}')
            raise UazapiServiceError(f'Erro de conexão: {e}') from e

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.get(url, params=params, headers=self._headers(), timeout=15)
            return resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {'raw': resp.text[:500]}
        except requests.RequestException as e:
            raise UazapiServiceError(f'Erro de conexão: {e}') from e

    # ── Envio de mensagens ──

    def enviar_texto(self, telefone, mensagem):
        """Envia mensagem de texto."""
        return self._post('/send/text', {
            'number': self._normalizar_telefone(telefone),
            'text': mensagem,
        })

    def enviar_imagem(self, telefone, url_imagem, legenda=''):
        """Envia imagem com legenda opcional."""
        return self.enviar_midia(telefone, url_imagem, 'image', legenda)

    def enviar_documento(self, telefone, url_documento, nome_arquivo='documento.pdf'):
        """Envia documento."""
        return self.enviar_midia(telefone, url_documento, 'document', nome_arquivo=nome_arquivo)

    def enviar_audio(self, telefone, url_audio):
        """Envia áudio."""
        return self.enviar_midia(telefone, url_audio, 'audio')

    def enviar_video(self, telefone, url_video, legenda=''):
        """Envia vídeo (MP4)."""
        return self.enviar_midia(telefone, url_video, 'video', legenda)

    def enviar_sticker(self, telefone, url_sticker):
        """Envia figurinha/sticker."""
        return self.enviar_midia(telefone, url_sticker, 'sticker')

    def enviar_voz(self, telefone, url_audio):
        """Envia mensagem de voz (PTT)."""
        return self.enviar_midia(telefone, url_audio, 'ptt')

    # ── Mídia unificada ──

    def enviar_midia(self, telefone, url_midia, tipo='image', legenda='', nome_arquivo=''):
        """
        Envia mídia via endpoint unificado /send/media.
        Tipos: image, video, videoplay, document, audio, myaudio, ptt, ptv, sticker
        """
        payload = {
            'number': self._normalizar_telefone(telefone),
            'type': tipo,
            'file': url_midia,
        }
        if legenda:
            payload['caption'] = legenda
        if nome_arquivo:
            payload['docName'] = nome_arquivo
        return self._post('/send/media', payload)

    # ── Menu interativo unificado (/send/menu) ──

    def enviar_menu(self, telefone, tipo, texto, choices, footer='', list_button='',
                    selectable_count=None, image_button='', **kwargs):
        """
        Endpoint unificado /send/menu para botões, listas, enquetes e carrossel.

        tipo: 'button', 'list', 'poll', 'carousel'
        texto: Texto principal da mensagem
        choices: Lista de opções (formato depende do tipo)
        footer: Texto do rodapé (opcional)
        list_button: Texto do botão que abre a lista (para tipo 'list')
        selectable_count: Máximo de opções selecionáveis (para tipo 'poll')
        image_button: URL de imagem para botões (para tipo 'button')

        Formato das choices por tipo:
            button: ["Texto|id", "Texto|url:https://...", "Texto|call:+55...", "Texto|copy:codigo"]
            list: ["[Seção]", "Item|id|descrição", ...]
            poll: ["Opção 1", "Opção 2", ...]
            carousel: ["[Texto do card]", "{url_imagem}", "Botão|action", ...]
        """
        payload = {
            'number': self._normalizar_telefone(telefone),
            'type': tipo,
            'text': texto,
            'choices': choices,
        }
        if footer:
            payload['footerText'] = footer
        if list_button:
            payload['listButton'] = list_button
        if selectable_count is not None:
            payload['selectableCount'] = selectable_count
        if image_button:
            payload['imageButton'] = image_button
        payload.update(kwargs)
        return self._post('/send/menu', payload)

    def enviar_botoes(self, telefone, texto, opcoes, footer='', imagem=''):
        """
        Atalho para enviar botões interativos.

        opcoes: ["Suporte|suporte", "Site|https://...", "Ligar|call:+55..."]
        """
        return self.enviar_menu(telefone, 'button', texto, opcoes, footer=footer, image_button=imagem)

    def enviar_lista(self, telefone, texto, opcoes, texto_botao='Ver opções', footer=''):
        """
        Atalho para enviar lista/menu.

        opcoes: ["[Seção]", "Item|id|descrição", ...]
        """
        return self.enviar_menu(telefone, 'list', texto, opcoes, footer=footer, list_button=texto_botao)

    def enviar_enquete(self, telefone, pergunta, opcoes, max_selecoes=1):
        """
        Atalho para enviar enquete.

        opcoes: ["Opção A", "Opção B", "Opção C"]
        """
        return self.enviar_menu(telefone, 'poll', pergunta, opcoes, selectable_count=max_selecoes)

    def enviar_carrossel(self, telefone, texto, cards):
        """
        Atalho para enviar carrossel.

        cards: ["[Título do card]", "{url_imagem}", "Botão|action", ...]
        """
        return self.enviar_menu(telefone, 'carousel', texto, cards)

    # ── Contato (vCard) ──

    def enviar_vcard(self, telefone, nome_contato, telefone_contato):
        """Envia cartão de contato (vCard)."""
        return self._post('/send/contact', {
            'number': self._normalizar_telefone(telefone),
            'contactName': nome_contato,
            'contactPhone': self._normalizar_telefone(telefone_contato),
        })

    # ── Localização ──

    def enviar_localizacao(self, telefone, latitude, longitude, nome='', endereco=''):
        """Envia localização geográfica."""
        return self._post('/send/location', {
            'number': self._normalizar_telefone(telefone),
            'lat': str(latitude),
            'lng': str(longitude),
            'name': nome,
            'address': endereco,
        })

    def solicitar_localizacao(self, telefone, mensagem='Compartilhe sua localização'):
        """Solicita localização do usuário."""
        return self._post('/send/requestLocation', {
            'number': self._normalizar_telefone(telefone),
            'text': mensagem,
        })

    # ── Presença ──

    def enviar_presenca(self, telefone, tipo='composing'):
        """Envia atualização de presença (composing, recording, available, unavailable)."""
        return self._post('/send/presence', {
            'number': self._normalizar_telefone(telefone),
            'type': tipo,
        })

    # ── Stories (Status) ──

    def enviar_story_texto(self, texto, cor_fundo='#000000'):
        """Publica story de texto."""
        return self._post('/send/stories', {
            'type': 'text',
            'text': texto,
            'backgroundColor': cor_fundo,
        })

    def enviar_story_midia(self, url_midia, tipo='image', legenda=''):
        """Publica story com mídia (imagem ou vídeo)."""
        return self._post('/send/stories', {
            'type': tipo,
            'file': url_midia,
            'caption': legenda,
        })

    # ── Pagamentos ──

    def solicitar_pagamento(self, telefone, valor, descricao='', moeda='BRL'):
        """Solicita pagamento."""
        return self._post('/send/requestPayment', {
            'number': self._normalizar_telefone(telefone),
            'amount': valor,
            'description': descricao,
            'currency': moeda,
        })

    def enviar_botao_pix(self, telefone, chave_pix, valor, descricao=''):
        """Envia botão PIX para pagamento."""
        return self._post('/send/pix', {
            'number': self._normalizar_telefone(telefone),
            'key': chave_pix,
            'amount': valor,
            'description': descricao,
        })

    # ── Consultas ──

    def status_instancia(self):
        """Verifica status da instância."""
        return self._get('/instance/status')

    def verificar_numero(self, telefone):
        """Verifica se o número está registrado no WhatsApp."""
        data = self._post('/misc/checkNumber', {
            'phone': self._normalizar_telefone(telefone),
        })
        return data.get('exists', False)

    def marcar_como_lido(self, remote_jid, message_id):
        """Marca mensagem como lida."""
        return self._post('/chat/markAsRead', {
            'remoteJid': remote_jid,
            'messageId': message_id,
        })

    # ── Helpers ──

    @staticmethod
    def _normalizar_telefone(telefone):
        """Remove caracteres não numéricos. Garante formato 55XXXXXXXXXXX."""
        import re
        numeros = re.sub(r'\D', '', str(telefone))
        if not numeros.startswith('55') and len(numeros) <= 11:
            numeros = '55' + numeros
        return numeros
