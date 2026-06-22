"""
Gancho do inbox → retoma execução de automação pausada esperando resposta.

Quando um contato manda uma mensagem, se houver uma execução pausada esperando a
resposta DELE, ela retoma (segue a saída `resposta`). BLINDADO: qualquer falha aqui
é engolida — nunca pode quebrar o fluxo do inbox/atendimento.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='inbox.Mensagem', dispatch_uid='automacao_retoma_resposta')
def on_mensagem_resposta(sender, instance, created, **kwargs):
    if not created or getattr(instance, 'remetente_tipo', '') != 'contato':
        return
    try:
        conversa = getattr(instance, 'conversa', None)
        if conversa is None:
            return
        from .execucao import retomar_por_resposta
        from .services.whatsapp import chave_telefone
        retomar_por_resposta(
            getattr(conversa, 'tenant', None),
            chave_telefone(getattr(conversa, 'contato_telefone', '') or ''),
            getattr(instance, 'conteudo', '') or '',
        )
    except Exception:
        logger.exception('[automacao] falha ao retomar execução por resposta')
