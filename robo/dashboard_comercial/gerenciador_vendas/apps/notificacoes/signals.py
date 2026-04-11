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
# LEAD CONVERTIDO (cadastro finalizado)
# ============================================================================

@receiver(post_save, sender='cadastro.CadastroCliente')
def notificar_lead_convertido(sender, instance, created, **kwargs):
    """Notifica quando um cadastro é finalizado (venda aprovada)."""
    if created:
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    if instance.status != 'finalizado':
        return

    try:
        from apps.notificacoes.services import criar_notificacao
        from django.contrib.auth.models import User

        tenant = instance.tenant
        nome = instance.nome_completo or 'Cliente'
        lead = instance.lead_gerado

        usuarios = User.objects.filter(
            perfil__tenant=tenant,
            is_active=True,
        ).exclude(perfil__cargo__in=['', None])

        for user in usuarios:
            criar_notificacao(
                tenant=tenant,
                codigo_tipo='venda_aprovada',
                titulo=f'Venda aprovada: {nome}',
                mensagem=f'Cadastro de {nome} foi finalizado com sucesso.',
                destinatario=user,
                url_acao=f'/comercial/leads/{lead.pk}/' if lead else '',
                dados_contexto={
                    'cadastro_id': instance.pk,
                    'cliente_nome': nome,
                    'lead_id': lead.pk if lead else None,
                },
            )
    except Exception as e:
        logger.error(f'Erro ao notificar lead convertido: {e}')


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
# MENSAGEM RECEBIDA (Inbox — mensagem de contato)
# ============================================================================

@receiver(post_save, sender='inbox.Mensagem')
def notificar_mensagem_recebida(sender, instance, created, **kwargs):
    """Notifica o agente quando recebe mensagem de um contato."""
    if not created:
        return

    if instance.remetente_tipo != 'contato':
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    try:
        from apps.notificacoes.services import criar_notificacao

        conversa = instance.conversa
        tenant = instance.tenant
        agente = conversa.agente

        if not agente:
            return

        nome = conversa.contato_nome or conversa.contato_telefone or 'Contato'
        preview = (instance.conteudo or '')[:100]

        criar_notificacao(
            tenant=tenant,
            codigo_tipo='mensagem_recebida',
            titulo=f'Nova mensagem: {nome}',
            mensagem=preview or 'Mensagem recebida.',
            destinatario=agente,
            url_acao=f'/inbox/{conversa.pk}/',
            dados_contexto={
                'conversa_id': conversa.pk,
                'mensagem_id': instance.pk,
                'contato_nome': nome,
            },
        )
    except Exception as e:
        logger.error(f'Erro ao notificar mensagem recebida: {e}')


# ============================================================================
# TAREFA ATRIBUÍDA (CRM)
# ============================================================================

@receiver(post_save, sender='crm.TarefaCRM')
def notificar_tarefa_atribuida(sender, instance, created, **kwargs):
    """Notifica o responsável quando uma tarefa é criada para ele."""
    if not created:
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    try:
        from apps.notificacoes.services import criar_notificacao

        responsavel = instance.responsavel
        criado_por = instance.criado_por

        # Só notifica se foi criada por outra pessoa
        if not responsavel or responsavel == criado_por:
            return

        tenant = instance.tenant

        criar_notificacao(
            tenant=tenant,
            codigo_tipo='tarefa_atribuida',
            titulo=f'Nova tarefa: {instance.titulo}',
            mensagem=f'Tarefa "{instance.titulo}" foi atribuída a você.',
            destinatario=responsavel,
            url_acao=f'/comercial/crm/tarefas/',
            prioridade=instance.prioridade,
            dados_contexto={
                'tarefa_id': instance.pk,
                'tarefa_titulo': instance.titulo,
                'criado_por': criado_por.username if criado_por else '',
            },
        )
    except Exception as e:
        logger.error(f'Erro ao notificar tarefa atribuída: {e}')


# ============================================================================
# OPORTUNIDADE MOVIDA DE ESTÁGIO (CRM)
# ============================================================================

@receiver(post_save, sender='crm.HistoricoPipelineEstagio')
def notificar_oportunidade_movida(sender, instance, created, **kwargs):
    """Notifica o responsável quando oportunidade muda de estágio."""
    if not created:
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    try:
        from apps.notificacoes.services import criar_notificacao

        oportunidade = instance.oportunidade
        responsavel = oportunidade.responsavel

        if not responsavel:
            return

        # Não notificar quem moveu
        if instance.movido_por and instance.movido_por == responsavel:
            return

        tenant = instance.tenant
        titulo_op = oportunidade.titulo or f'Oportunidade #{oportunidade.pk}'
        estagio_novo = instance.estagio_novo.nome if instance.estagio_novo else 'Desconhecido'

        criar_notificacao(
            tenant=tenant,
            codigo_tipo='oportunidade_movida',
            titulo=f'Oportunidade movida: {titulo_op}',
            mensagem=f'{titulo_op} foi movida para o estágio "{estagio_novo}".',
            destinatario=responsavel,
            url_acao=f'/comercial/crm/',
            dados_contexto={
                'oportunidade_id': oportunidade.pk,
                'estagio_novo': estagio_novo,
                'estagio_anterior': instance.estagio_anterior.nome if instance.estagio_anterior else '',
                'movido_por': instance.movido_por.username if instance.movido_por else '',
            },
        )
    except Exception as e:
        logger.error(f'Erro ao notificar oportunidade movida: {e}')


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

        if instance.atendente:
            criar_notificacao(
                tenant=tenant,
                codigo_tipo='ticket_criado',
                titulo=f'Novo ticket: {instance.titulo}',
                mensagem=f'Ticket #{instance.numero} foi aberto.',
                destinatario=instance.atendente,
                url_acao=f'/suporte/tickets/{instance.pk}/',
                dados_contexto={
                    'ticket_id': instance.pk,
                    'ticket_titulo': instance.titulo,
                    'ticket_numero': instance.numero,
                },
            )
    except Exception as e:
        logger.error(f'Erro ao notificar ticket criado: {e}')


# ============================================================================
# TICKET RESPONDIDO (Suporte — novo comentário)
# ============================================================================

@receiver(post_save, sender='suporte.ComentarioTicket')
def notificar_ticket_respondido(sender, instance, created, **kwargs):
    """Notifica quando um comentário é adicionado ao ticket."""
    if not created:
        return

    if getattr(instance, '_skip_notificacao', False):
        return

    if instance.interno:
        return

    try:
        from apps.notificacoes.services import criar_notificacao

        ticket = instance.ticket
        autor = instance.autor
        tenant = instance.tenant

        # Notificar o solicitante (se não foi ele quem comentou)
        if ticket.solicitante and ticket.solicitante != autor:
            criar_notificacao(
                tenant=tenant,
                codigo_tipo='ticket_respondido',
                titulo=f'Ticket #{ticket.numero} respondido',
                mensagem=f'Novo comentário no ticket "{ticket.titulo}".',
                destinatario=ticket.solicitante,
                url_acao=f'/suporte/tickets/{ticket.pk}/',
                dados_contexto={
                    'ticket_id': ticket.pk,
                    'ticket_numero': ticket.numero,
                    'autor': autor.username if autor else '',
                },
            )

        # Notificar o atendente (se não foi ele quem comentou)
        if ticket.atendente and ticket.atendente != autor and ticket.atendente != ticket.solicitante:
            criar_notificacao(
                tenant=tenant,
                codigo_tipo='ticket_respondido',
                titulo=f'Ticket #{ticket.numero} respondido',
                mensagem=f'Novo comentário no ticket "{ticket.titulo}".',
                destinatario=ticket.atendente,
                url_acao=f'/suporte/tickets/{ticket.pk}/',
                dados_contexto={
                    'ticket_id': ticket.pk,
                    'ticket_numero': ticket.numero,
                    'autor': autor.username if autor else '',
                },
            )
    except Exception as e:
        logger.error(f'Erro ao notificar ticket respondido: {e}')
