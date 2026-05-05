"""
Notifica agentes quando conversas no Inbox estão sem resposta há muito tempo.

Detecta Conversa com:
- status='aberta'
- ultima_mensagem_em < agora - sla_horas
- ainda não notificou esta conversa nas últimas X horas

Cria notificação in-app via tipo 'sla_estourando'.

Uso:
    python manage.py notificar_sla_inbox --settings=gerenciador_vendas.settings_local --horas=2

Crontab sugerido (a cada 15 min):
    */15 * * * * python manage.py notificar_sla_inbox --horas=2
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Notifica conversas do Inbox sem resposta há mais de X horas'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--horas',
            type=int,
            default=2,
            help='SLA em horas. Conversas sem resposta há mais que isso disparam notificação (default: 2)',
        )

    def handle(self, *args, **options):
        from apps.inbox.models import Conversa, Mensagem
        from apps.notificacoes.models import Notificacao
        from apps.notificacoes.services import criar_notificacao

        dry = options['dry_run']
        horas = options['horas']
        agora = timezone.now()
        limite = agora - timedelta(hours=horas)
        janela_antispam = agora - timedelta(hours=horas)

        # Conversas abertas com agente atribuído
        candidatas = (
            Conversa.objects
            .filter(status='aberta', agente__isnull=False)
            .select_related('agente', 'tenant')
        )

        criadas = 0
        puladas_anti_spam = 0
        ignoradas_sem_atraso = 0
        for conv in candidatas:
            # Última mensagem do cliente (in)
            ultima_in = (
                Mensagem.objects
                .filter(conversa=conv, remetente_tipo='cliente')
                .order_by('-criado_em')
                .first()
            )
            ultima_out = (
                Mensagem.objects
                .filter(conversa=conv, remetente_tipo__in=['agente', 'bot'])
                .order_by('-criado_em')
                .first()
            )

            if not ultima_in:
                ignoradas_sem_atraso += 1
                continue

            # Se a última de saída é mais recente que a última de entrada → respondeu
            if ultima_out and ultima_out.criado_em > ultima_in.criado_em:
                ignoradas_sem_atraso += 1
                continue

            if ultima_in.criado_em > limite:
                ignoradas_sem_atraso += 1
                continue

            # Anti-spam
            ja_notificou = Notificacao.objects.filter(
                tenant=conv.tenant,
                destinatario=conv.agente,
                tipo__codigo='sla_estourando',
                criado_em__gte=janela_antispam,
                dados_contexto__conversa_id=conv.id,
            ).exists()
            if ja_notificou:
                puladas_anti_spam += 1
                continue

            horas_atraso = (agora - ultima_in.criado_em).total_seconds() / 3600
            corpo = (
                f'Conversa #{conv.numero} ({conv.contato_nome or "sem nome"}) '
                f'sem resposta há {horas_atraso:.1f}h'
            )

            if dry:
                self.stdout.write(f'[DRY] {conv.agente.username} ← {corpo}')
                continue

            n = criar_notificacao(
                tenant=conv.tenant,
                codigo_tipo='sla_estourando',
                titulo='SLA do atendimento estourando',
                mensagem=corpo,
                destinatario=conv.agente,
                url_acao=f'/inbox/?conversa={conv.id}',
                dados_contexto={'conversa_id': conv.id, 'horas_atraso': round(horas_atraso, 2)},
            )
            if n:
                criadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\nConversas inspecionadas: {candidatas.count()} | '
                f'Notificações criadas: {criadas} | '
                f'Puladas (anti-spam): {puladas_anti_spam} | '
                f'Ignoradas (sem atraso): {ignoradas_sem_atraso} | '
                f'Modo: {"dry-run" if dry else "aplicado"}'
            )
        )
