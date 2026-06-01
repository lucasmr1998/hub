"""Signals do app Suporte — regera embedding do artigo quando texto muda.

Mantemos o processamento sincrono dentro do save (1 call OpenAI, ~300ms).
Se virar gargalo no futuro, dispara em background via thread/celery.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


_CAMPOS_QUE_AFETAM_EMBEDDING = ('titulo', 'conteudo', 'tags', 'resumo')


@receiver(pre_save, sender='suporte.ArtigoConhecimento')
def _marcar_se_texto_mudou(sender, instance, **kwargs):
    """Pre-save: detecta se algum campo de texto mudou pra decidir se regera
    embedding no post_save. Usa flag _embedding_precisa_regerar no instance."""
    if not instance.pk:
        # Novo artigo — sempre regera
        instance._embedding_precisa_regerar = True
        return
    try:
        atual = sender.all_tenants.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._embedding_precisa_regerar = True
        return
    instance._embedding_precisa_regerar = any(
        getattr(atual, c, None) != getattr(instance, c, None)
        for c in _CAMPOS_QUE_AFETAM_EMBEDDING
    ) or atual.embedding is None


@receiver(post_save, sender='suporte.ArtigoConhecimento')
def _regerar_embedding(sender, instance, created, **kwargs):
    if not getattr(instance, '_embedding_precisa_regerar', True if created else False):
        return
    # Evita loop quando o proprio signal salva o embedding
    if getattr(instance, '_atualizando_embedding', False):
        return
    from apps.sistema.services.embeddings import gerar_embedding
    texto = instance.texto_pra_embedding()
    emb = gerar_embedding(texto, tenant=instance.tenant)
    if emb is None:
        logger.warning(
            'post_save ArtigoConhecimento %s: embedding nao gerado (sem creds OpenAI?)',
            instance.pk,
        )
        return
    instance._atualizando_embedding = True
    try:
        sender.all_tenants.filter(pk=instance.pk).update(
            embedding=emb, embedding_atualizado_em=timezone.now(),
        )
    finally:
        instance._atualizando_embedding = False
