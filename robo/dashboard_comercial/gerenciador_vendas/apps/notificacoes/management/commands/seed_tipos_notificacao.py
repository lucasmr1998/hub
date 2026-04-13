"""
Seed de tipos e canais de notificacao para cada tenant.
Idempotente: so cria o que nao existe.
"""
from django.core.management.base import BaseCommand
from apps.sistema.models import Tenant
from apps.notificacoes.models import TipoNotificacao, CanalNotificacao


TIPOS = [
    ('lead_novo', 'Novo Lead', 'Notifica quando um novo lead e capturado', 'normal', 'fas fa-user-plus'),
    ('lead_convertido', 'Lead Convertido', 'Notifica quando um lead e convertido em cliente', 'normal', 'fas fa-check-circle'),
    ('venda_aprovada', 'Venda Aprovada', 'Notifica quando uma venda e aprovada', 'alta', 'fas fa-thumbs-up'),
    ('venda_rejeitada', 'Venda Rejeitada', 'Notifica quando uma venda e rejeitada', 'alta', 'fas fa-times-circle'),
    ('prospecto_aguardando', 'Prospecto Aguardando', 'Prospecto aguardando validacao', 'normal', 'fas fa-clock'),
    ('conversa_recebida', 'Nova Conversa Recebida', 'Nova conversa chegou no inbox', 'normal', 'fas fa-comment-dots'),
    ('conversa_transferida', 'Conversa Transferida', 'Conversa foi transferida para voce', 'alta', 'fas fa-exchange-alt'),
    ('mensagem_recebida', 'Nova Mensagem', 'Nova mensagem de contato', 'normal', 'fas fa-envelope'),
    ('tarefa_vencendo', 'Tarefa Proxima do Vencimento', 'Tarefa com vencimento proximo', 'alta', 'fas fa-exclamation-triangle'),
    ('tarefa_atribuida', 'Tarefa Atribuida', 'Uma tarefa foi atribuida a voce', 'normal', 'fas fa-tasks'),
    ('oportunidade_movida', 'Oportunidade Mudou de Estagio', 'Oportunidade foi movida no pipeline', 'normal', 'fas fa-columns'),
    ('ticket_criado', 'Novo Ticket', 'Um novo ticket de suporte foi criado', 'normal', 'fas fa-ticket-alt'),
    ('ticket_respondido', 'Ticket Respondido', 'Um ticket recebeu resposta', 'normal', 'fas fa-reply'),
    ('sla_estourando', 'SLA Proximo do Limite', 'SLA de um ticket esta perto de estourar', 'urgente', 'fas fa-fire'),
    ('mencao_nota', 'Mencao em Nota', 'Voce foi mencionado em uma nota', 'normal', 'fas fa-at'),
    ('sistema_geral', 'Notificacao do Sistema', 'Notificacao geral do sistema', 'normal', 'fas fa-bell'),
]

CANAIS = [
    ('sistema', 'Sistema (in-app)', 'fas fa-bell'),
    ('email', 'Email', 'fas fa-envelope'),
    ('whatsapp', 'WhatsApp', 'fab fa-whatsapp'),
    ('webhook', 'Webhook', 'fas fa-plug'),
]


class Command(BaseCommand):
    help = 'Cria tipos e canais de notificacao para cada tenant (idempotente).'

    def handle(self, *args, **options):
        tenants = Tenant.objects.filter(ativo=True)
        tipos_criados = 0
        canais_criados = 0

        for tenant in tenants:
            for codigo, nome, descricao, prioridade, icone in TIPOS:
                _, created = TipoNotificacao.all_tenants.get_or_create(
                    tenant=tenant,
                    codigo=codigo,
                    defaults={
                        'nome': nome,
                        'descricao': descricao,
                        'prioridade_padrao': prioridade,
                        'icone': icone,
                        'template_padrao': '',
                    }
                )
                if created:
                    tipos_criados += 1

            for codigo, nome, icone in CANAIS:
                _, created = CanalNotificacao.all_tenants.get_or_create(
                    tenant=tenant,
                    codigo=codigo,
                    defaults={'nome': nome, 'icone': icone},
                )
                if created:
                    canais_criados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Notificacoes: {tipos_criados} tipos e {canais_criados} canais criados para {tenants.count()} tenant(s)'
        ))
