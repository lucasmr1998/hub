import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ============================================================================
# LEAD NOVO
# ============================================================================

@receiver(post_save, sender='leads.LeadProspecto')
def notificar_lead_novo(sender, instance, created, **kwargs):
    """Notifica usuários quando um novo lead é capturado."""
    if not created:
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    try:
        from apps.notificacoes.services import criar_notificacao
        from django.contrib.auth.models import User

        tenant = instance.tenant
        nome = instance.nome_razaosocial or 'Sem nome'
        telefone = instance.telefone or ''

        usuarios = User.objects.filter(
            perfil__tenant=tenant,
            is_active=True,
        ).exclude(perfil__cargo__in=['', None])

        for user in usuarios:
            criar_notificacao(
                tenant=tenant,
                codigo_tipo='lead_novo',
                titulo=f'Novo lead: {nome}',
                mensagem=f'Lead {nome} ({telefone}) foi capturado.',
                destinatario=user,
                url_acao=f'/comercial/leads/{instance.pk}/',
                dados_contexto={
                    'lead_id': instance.pk,
                    'lead_nome': nome,
                    'lead_telefone': telefone,
                },
            )
    except Exception as e:
        logger.error(f'Erro ao notificar lead novo: {e}')


# ============================================================================
# CONVERSA RECEBIDA (Inbox)
# ============================================================================

@receiver(post_save, sender='inbox.Conversa')
def notificar_conversa_recebida(sender, instance, created, **kwargs):
    """Notifica quando nova conversa chega no inbox."""
    if not created:
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    try:
        from apps.notificacoes.services import criar_notificacao

        tenant = instance.tenant
        nome = instance.contato_nome or instance.contato_telefone or 'Contato'

        if instance.agente:
            criar_notificacao(
                tenant=tenant,
                codigo_tipo='conversa_recebida',
                titulo=f'Nova conversa: {nome}',
                mensagem=f'Nova conversa de {nome} foi aberta.',
                destinatario=instance.agente,
                url_acao=f'/inbox/{instance.pk}/',
                dados_contexto={
                    'conversa_id': instance.pk,
                    'contato_nome': nome,
                },
            )
    except Exception as e:
        logger.error(f'Erro ao notificar conversa recebida: {e}')


# ============================================================================
# CONVERSA TRANSFERIDA (mudança de agente)
# ============================================================================

@receiver(post_save, sender='inbox.Conversa')
def notificar_conversa_transferida(sender, instance, created, **kwargs):
    """Notifica agente quando recebe uma conversa transferida."""
    if created:
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    # _agente_anterior é setado por quem faz a transferência (view/service)
    agente_anterior = getattr(instance, '_agente_anterior', None)
    novo_agente = instance.agente

    if not novo_agente or novo_agente == agente_anterior:
        return

    if agente_anterior is None:
        return

    try:
        from apps.notificacoes.services import criar_notificacao

        tenant = instance.tenant
        nome = instance.contato_nome or instance.contato_telefone or 'Contato'

        criar_notificacao(
            tenant=tenant,
            codigo_tipo='conversa_transferida',
            titulo=f'Conversa transferida: {nome}',
            mensagem=f'A conversa de {nome} foi transferida para você.',
            destinatario=novo_agente,
            url_acao=f'/inbox/{instance.pk}/',
            prioridade='alta',
            dados_contexto={
                'conversa_id': instance.pk,
                'contato_nome': nome,
            },
        )
    except Exception as e:
        logger.error(f'Erro ao notificar conversa transferida: {e}')


# ============================================================================
# TICKET CRIADO (Suporte)
# ============================================================================

@receiver(post_save, sender='suporte.Ticket')
def notificar_ticket_criado(sender, instance, created, **kwargs):
    """Notifica quando novo ticket é aberto."""
    if not created:
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    try:
        from apps.notificacoes.services import criar_notificacao

        tenant = instance.tenant

        if instance.atribuido_a:
            criar_notificacao(
                tenant=tenant,
                codigo_tipo='ticket_criado',
                titulo=f'Novo ticket: {instance.titulo}',
                mensagem=f'Ticket #{instance.pk} foi aberto.',
                destinatario=instance.atribuido_a,
                url_acao=f'/suporte/tickets/{instance.pk}/',
                dados_contexto={
                    'ticket_id': instance.pk,
                    'ticket_titulo': instance.titulo,
                },
            )
    except Exception as e:
        logger.error(f'Erro ao notificar ticket criado: {e}')
