"""
Notifica responsáveis quando suas tarefas CRM estão prestes a vencer.

Detecta TarefaCRM com:
- status pendente ou em_andamento
- data_vencimento entre [agora, agora + 24h]
- ainda não notificada nas últimas 24h (anti-spam)

Cria notificação in-app via tipo 'tarefa_vencendo'.

Uso:
    python manage.py notificar_tarefas_vencendo --settings=gerenciador_vendas.settings_local

Crontab sugerido (a cada 30 min):
    */30 * * * * python manage.py notificar_tarefas_vencendo
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cria notificações para tarefas CRM próximas do vencimento'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--horas',
            type=int,
            default=24,
            help='Janela de antecedência em horas (default: 24)',
        )

    def handle(self, *args, **options):
        from apps.comercial.crm.models import TarefaCRM
        from apps.notificacoes.models import Notificacao
        from apps.notificacoes.services import criar_notificacao

        dry = options['dry_run']
        horas = options['horas']
        agora = timezone.now()
        limite = agora + timedelta(hours=horas)
        janela_antispam = agora - timedelta(hours=horas)

        # Tarefas no horizonte de timeout
        candidatas = TarefaCRM.objects.filter(
            status__in=['pendente', 'em_andamento'],
            data_vencimento__gte=agora,
            data_vencimento__lte=limite,
            responsavel__isnull=False,
        ).select_related('responsavel', 'lead', 'tenant')

        criadas = 0
        puladas_anti_spam = 0
        for tarefa in candidatas:
            # Anti-spam: ja notificou nas últimas X horas?
            ja_notificou = Notificacao.objects.filter(
                tenant=tarefa.tenant,
                destinatario=tarefa.responsavel,
                tipo__codigo='tarefa_vencendo',
                criado_em__gte=janela_antispam,
                dados_contexto__tarefa_id=tarefa.id,
            ).exists()
            if ja_notificou:
                puladas_anti_spam += 1
                continue

            horas_pra_vencer = max(0, int((tarefa.data_vencimento - agora).total_seconds() / 3600))
            lead_nome = tarefa.lead.nome_razaosocial if tarefa.lead else None
            corpo = (
                f'"{tarefa.titulo}" vence em {horas_pra_vencer}h'
                + (f' (lead: {lead_nome})' if lead_nome else '')
            )

            if dry:
                self.stdout.write(f'[DRY] {tarefa.responsavel.username} ← {corpo}')
                continue

            n = criar_notificacao(
                tenant=tarefa.tenant,
                codigo_tipo='tarefa_vencendo',
                titulo='Tarefa próxima do vencimento',
                mensagem=corpo,
                destinatario=tarefa.responsavel,
                # nao existe rota de detalhe de tarefa. As rotas sao lista, criar e concluir.
                # O link antigo (/crm/tarefas/<id>/) caia em 404.
                url_acao='/crm/tarefas/',
                dados_contexto={'tarefa_id': tarefa.id, 'horas_pra_vencer': horas_pra_vencer},
            )
            if n:
                criadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nTarefas inspecionadas: {candidatas.count()} | '
                f'Notificações criadas: {criadas} | '
                f'Puladas (anti-spam): {puladas_anti_spam} | '
                f'Modo: {"dry-run" if dry else "aplicado"}'
            )
        )
