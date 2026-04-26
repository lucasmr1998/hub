"""
Seeds canonicos de Tipos e Canais de notificacao.

Quando um Tenant novo eh criado, esses tipos/canais sao replicados pra ele
via signal post_save em apps.notificacoes.signals_tenant. Tipos podem ser
customizados depois pelo tenant (template, prioridade, ativo) sem afetar
outros tenants.
"""

# (codigo, nome, descricao, prioridade_padrao, icone, categoria)
TIPOS_PADRAO = [
    # Comercial
    ('lead_novo', 'Lead novo capturado', 'Disparado quando um novo lead chega.', 'normal', 'fas fa-user-plus', 'Comercial'),
    ('lead_convertido', 'Lead convertido', 'Lead virou cliente.', 'alta', 'fas fa-check-circle', 'Comercial'),
    ('venda_aprovada', 'Venda aprovada', 'Venda foi aprovada (cadastro finalizado).', 'alta', 'fas fa-money-bill-wave', 'Comercial'),
    ('venda_rejeitada', 'Venda rejeitada', 'Venda foi rejeitada/recusada.', 'normal', 'fas fa-times-circle', 'Comercial'),
    ('prospecto_aguardando', 'Prospecto aguardando', 'Prospecto aguardando atendimento.', 'normal', 'fas fa-hourglass-half', 'Comercial'),

    # Inbox
    ('conversa_recebida', 'Conversa recebida', 'Nova conversa com agente atribuido.', 'normal', 'fas fa-comment-dots', 'Inbox'),
    ('conversa_transferida', 'Conversa transferida', 'Conversa transferida pra voce.', 'alta', 'fas fa-exchange-alt', 'Inbox'),
    ('mensagem_recebida', 'Mensagem recebida', 'Nova mensagem em conversa atribuida.', 'normal', 'fas fa-envelope', 'Inbox'),

    # CRM
    ('tarefa_vencendo', 'Tarefa vencendo', 'Tarefa proxima do vencimento.', 'alta', 'fas fa-clock', 'CRM'),
    ('tarefa_atribuida', 'Tarefa atribuida', 'Voce foi designado pra uma tarefa.', 'normal', 'fas fa-tasks', 'CRM'),
    ('oportunidade_movida', 'Oportunidade movida', 'Oportunidade mudou de estagio no pipeline.', 'normal', 'fas fa-arrow-right', 'CRM'),

    # Suporte
    ('ticket_criado', 'Ticket criado', 'Novo ticket atribuido a voce.', 'normal', 'fas fa-ticket-alt', 'Suporte'),
    ('ticket_respondido', 'Ticket respondido', 'Resposta nova em ticket que voce participa.', 'normal', 'fas fa-reply', 'Suporte'),
    ('sla_estourando', 'SLA estourando', 'Ticket proximo do prazo de SLA.', 'urgente', 'fas fa-exclamation-triangle', 'Suporte'),

    # Sistema
    ('mencao_nota', 'Mencao em nota', 'Voce foi mencionado em uma nota.', 'normal', 'fas fa-at', 'Sistema'),
    ('sistema_geral', 'Aviso do sistema', 'Aviso geral do sistema.', 'normal', 'fas fa-info-circle', 'Sistema'),
    ('integracao_quebrada', 'Integracao quebrada', 'Integracao com API externa falhando.', 'urgente', 'fas fa-plug', 'Sistema'),
]

# (codigo, nome, icone)
CANAIS_PADRAO = [
    ('sistema', 'Sistema (in-app)', 'fas fa-bell'),
    ('email', 'Email', 'fas fa-envelope'),
    ('whatsapp', 'WhatsApp', 'fab fa-whatsapp'),
    ('webhook', 'Webhook', 'fas fa-code'),
]


def seed_tenant(tenant):
    """Cria/garante todos os tipos e canais padrao pro tenant.

    Idempotente: usa get_or_create. Pode ser rodado varias vezes sem
    duplicar. Tipos/canais existentes nao sao alterados (preserva
    customizacoes do tenant).

    Returns: dict com contagem do que foi criado.
    """
    from apps.notificacoes.models import TipoNotificacao, CanalNotificacao

    tipos_criados = 0
    canais_criados = 0

    for codigo, nome, descricao, prioridade, icone, _categoria in TIPOS_PADRAO:
        _, criado = TipoNotificacao.objects.get_or_create(
            tenant=tenant,
            codigo=codigo,
            defaults={
                'nome': nome,
                'descricao': descricao,
                'prioridade_padrao': prioridade,
                'icone': icone,
                'ativo': True,
            },
        )
        if criado:
            tipos_criados += 1

    for codigo, nome, icone in CANAIS_PADRAO:
        _, criado = CanalNotificacao.objects.get_or_create(
            tenant=tenant,
            codigo=codigo,
            defaults={
                'nome': nome,
                'icone': icone,
                'ativo': codigo == 'sistema',  # so 'sistema' ativo por padrao; outros precisam config
            },
        )
        if criado:
            canais_criados += 1

    return {'tipos_criados': tipos_criados, 'canais_criados': canais_criados}
