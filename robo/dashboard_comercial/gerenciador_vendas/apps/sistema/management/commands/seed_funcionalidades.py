from django.core.management.base import BaseCommand
from apps.sistema.models import Funcionalidade


FUNCIONALIDADES = [
    # ── COMERCIAL ──
    ('comercial', 'comercial.ver_dashboard', 'Ver Dashboard', 'Acesso ao dashboard comercial', 1),
    ('comercial', 'comercial.ver_pipeline', 'Ver Pipeline', 'Visualizar pipeline Kanban e oportunidades', 2),
    ('comercial', 'comercial.mover_oportunidade', 'Mover Oportunidades', 'Arrastar oportunidades entre estágios', 3),
    ('comercial', 'comercial.ver_todas_oportunidades', 'Ver Todas as Oportunidades', 'Ver oportunidades de todos os vendedores (escopo equipe/todos)', 4),
    ('comercial', 'comercial.criar_tarefa', 'Criar e Editar Tarefas', 'Criar, editar e concluir tarefas no CRM', 5),
    ('comercial', 'comercial.ver_desempenho', 'Ver Relatórios de Desempenho', 'Acessar dashboard de performance por vendedor', 6),
    ('comercial', 'comercial.gerenciar_metas', 'Gerenciar Metas', 'Criar, editar e excluir metas de vendas', 7),
    ('comercial', 'comercial.gerenciar_equipes', 'Gerenciar Equipes', 'Criar equipes e atribuir membros', 8),
    ('comercial', 'comercial.configurar_pipeline', 'Configurar Pipelines', 'Criar/editar pipelines, estágios, webhooks e configurações do CRM', 9),

    # ── MARKETING ──
    ('marketing', 'marketing.ver_leads', 'Ver Leads', 'Visualizar lista de leads e detalhes', 1),
    ('marketing', 'marketing.gerenciar_campanhas', 'Gerenciar Campanhas', 'Criar, editar e excluir campanhas de tráfego', 2),
    ('marketing', 'marketing.ver_segmentos', 'Ver Segmentos', 'Visualizar segmentos e membros', 3),
    ('marketing', 'marketing.gerenciar_segmentos', 'Gerenciar Segmentos', 'Criar, editar segmentos e regras de filtro', 4),
    ('marketing', 'marketing.ver_automacoes', 'Ver Automações', 'Visualizar lista de automações e histórico', 5),
    ('marketing', 'marketing.gerenciar_automacoes', 'Gerenciar Automações', 'Criar, editar e configurar automações no editor visual', 6),
    ('marketing', 'marketing.configurar', 'Configurar Marketing', 'Landing page, ativar/desativar automações, integrações', 7),

    # ── CUSTOMER SUCCESS ──
    ('cs', 'cs.ver_dashboard', 'Ver Dashboard CS', 'Acesso ao dashboard do Clube', 1),
    ('cs', 'cs.gerenciar_membros', 'Gerenciar Membros', 'Ver, editar saldo e extrato de membros', 2),
    ('cs', 'cs.gerenciar_cupons', 'Gerenciar Cupons e Parceiros', 'CRUD de parceiros, cupons e resgates', 3),
    ('cs', 'cs.aprovar_cupons', 'Aprovar/Rejeitar Cupons', 'Aprovar ou rejeitar cupons de parceiros', 4),
    ('cs', 'cs.gerenciar_indicacoes', 'Gerenciar Indicações', 'Ver, alterar status e converter indicações', 5),
    ('cs', 'cs.configurar', 'Configurar CS', 'Regras de pontuação, níveis, banners, carteirinhas, landing page', 6),

    # ── INBOX / SUPORTE ──
    ('inbox', 'inbox.ver_minhas', 'Ver Minhas Conversas', 'Ver apenas conversas atribuídas a mim', 1),
    ('inbox', 'inbox.ver_equipe', 'Ver Conversas da Equipe', 'Ver conversas de toda a equipe (escopo supervisor)', 2),
    ('inbox', 'inbox.ver_todas', 'Ver Todas as Conversas', 'Ver todas as conversas do tenant', 3),
    ('inbox', 'inbox.responder', 'Responder Conversas', 'Enviar mensagens e notas privadas', 4),
    ('inbox', 'inbox.transferir_agente', 'Transferir para Agente', 'Transferir conversa para outro agente', 5),
    ('inbox', 'inbox.transferir_equipe', 'Transferir entre Equipes', 'Transferir conversa para outra equipe/fila', 6),
    ('inbox', 'inbox.resolver', 'Resolver e Reabrir', 'Resolver, marcar pendente ou reabrir conversas', 7),
    ('inbox', 'inbox.configurar', 'Configurar Inbox', 'Equipes, filas, horários, canais, respostas rápidas, widget', 8),

    # ── CONFIGURAÇÕES ──
    ('configuracoes', 'config.gerenciar_usuarios', 'Gerenciar Usuários', 'Criar, editar e excluir usuários do sistema', 1),
    ('configuracoes', 'config.gerenciar_perfis', 'Gerenciar Perfis de Permissão', 'Criar e editar perfis de permissão', 2),
    ('configuracoes', 'config.gerenciar_planos', 'Gerenciar Planos e Vencimentos', 'CRUD de planos de internet e opções de vencimento', 3),
    ('configuracoes', 'config.gerenciar_fluxos', 'Gerenciar Fluxos de Atendimento', 'Configurar fluxos e questões do bot', 4),
    ('configuracoes', 'config.gerenciar_notificacoes', 'Gerenciar Notificações', 'Configurar tipos e canais de notificação', 5),
]


class Command(BaseCommand):
    help = 'Cria/atualiza as funcionalidades do sistema (seed fixo).'

    def handle(self, *args, **options):
        criadas = 0
        atualizadas = 0

        for modulo, codigo, nome, descricao, ordem in FUNCIONALIDADES:
            _, created = Funcionalidade.objects.update_or_create(
                codigo=codigo,
                defaults={
                    'modulo': modulo,
                    'nome': nome,
                    'descricao': descricao,
                    'ordem': ordem,
                },
            )
            if created:
                criadas += 1
            else:
                atualizadas += 1

        total = len(FUNCIONALIDADES)
        self.stdout.write(self.style.SUCCESS(
            f'Funcionalidades: {total} total, {criadas} criada(s), {atualizadas} atualizada(s).'
        ))
