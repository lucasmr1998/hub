"""Signal: quando uma RegraValidacao é editada, notifica a API IA externa
pra invalidar o cache em memória.
"""
import logging
import os

import httpx
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import RegraValidacao

logger = logging.getLogger(__name__)

# Configurável via env var (definir no Django settings ou export)
IA_API_URL = os.getenv('IA_VALIDACAO_URL', 'http://localhost:8090')


def _notificar_invalidacao():
    """Chama o endpoint da API IA pra zerar o cache. Falha silenciosa."""
    try:
        httpx.post(f'{IA_API_URL}/admin/invalidar-cache/', timeout=2.0)
    except Exception as e:
        logger.warning(f'Falha ao invalidar cache da API IA: {e}')


@receiver(post_save, sender=RegraValidacao)
def regra_salva(sender, instance, **kwargs):
    _notificar_invalidacao()


@receiver(post_delete, sender=RegraValidacao)
def regra_deletada(sender, instance, **kwargs):
    _notificar_invalidacao()
