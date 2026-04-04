"""
Signals do Inbox para integração com o engine de automações.

Dispara eventos quando:
- Nova conversa é criada
- Mensagem de contato é recebida
- Conversa é resolvida
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='inbox.Conversa')
def on_conversa_criada(sender, instance, created, **kwargs):
    """Dispara evento 'conversa_aberta' quando nova conversa é criada."""
    if not created:
        return

    if getattr(instance, '_skip_automacao', False):
        return

    try:
        from apps.marketing.automacoes.engine import disparar_evento

        contexto = {
            'conversa': instance,
            'lead': instance.lead,
            'telefone': instance.contato_telefone,
            'nome': instance.contato_nome,
            'canal': instance.canal.tipo if instance.canal_id else '',
        }

        if instance.lead:
            contexto.update({
                'lead_nome': instance.lead.nome_razaosocial,
                'lead_telefone': instance.lead.telefone,
                'lead_email': instance.lead.email or '',
            })

        disparar_evento('conversa_aberta', contexto, tenant=instance.tenant)
    except Exception as e:
        logger.error("Erro ao disparar automação conversa_aberta: %s", e)


@receiver(post_save, sender='inbox.Mensagem')
def on_mensagem_recebida(sender, instance, created, **kwargs):
    """Dispara evento 'mensagem_recebida' para mensagens de contato."""
    if not created:
        return

    if instance.remetente_tipo != 'contato':
        return

    if getattr(instance, '_skip_automacao', False):
        return

    try:
        from apps.marketing.automacoes.engine import disparar_evento

        conversa = instance.conversa
        contexto = {
            'conversa': conversa,
            'mensagem': instance,
            'lead': conversa.lead,
            'telefone': conversa.contato_telefone,
            'nome': conversa.contato_nome,
            'conteudo': instance.conteudo[:200],
            'canal': conversa.canal.tipo if conversa.canal_id else '',
        }

        if conversa.lead:
            contexto.update({
                'lead_nome': conversa.lead.nome_razaosocial,
                'lead_telefone': conversa.lead.telefone,
                'lead_email': conversa.lead.email or '',
            })

        disparar_evento('mensagem_recebida', contexto, tenant=instance.tenant)
    except Exception as e:
        logger.error("Erro ao disparar automação mensagem_recebida: %s", e)


@receiver(post_save, sender='inbox.Conversa')
def on_conversa_resolvida(sender, instance, created, **kwargs):
    """Dispara evento 'conversa_resolvida' quando conversa muda para resolvida."""
    if created:
        return

    if instance.status != 'resolvida':
        return

    if getattr(instance, '_skip_automacao', False):
        return

    try:
        from apps.marketing.automacoes.engine import disparar_evento

        contexto = {
            'conversa': instance,
            'lead': instance.lead,
            'telefone': instance.contato_telefone,
            'nome': instance.contato_nome,
        }

        if instance.lead:
            contexto.update({
                'lead_nome': instance.lead.nome_razaosocial,
                'lead_telefone': instance.lead.telefone,
            })

        disparar_evento('conversa_resolvida', contexto, tenant=instance.tenant)
    except Exception as e:
        logger.error("Erro ao disparar automação conversa_resolvida: %s", e)
