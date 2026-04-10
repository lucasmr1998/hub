"""
Cron de verificacao de SLA e escalacao automatica.

Detecta tickets com SLA prestes a estourar ou ja estourado.
Registra alerta no historico e escala se necessario.

Uso:
    python manage.py verificar_sla --settings=gerenciador_vendas.settings_local_pg

Crontab (a cada 15 minutos):
    */15 * * * * cd /path/to/project && python manage.py verificar_sla
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Verifica SLA dos tickets e escala se necessario'

    def handle(self, *args, **options):
        from apps.sistema.models import Tenant
        from apps.sistema.middleware import set_current_tenant

        total_alertas = 0
        total_escalados = 0

        for tenant in Tenant.objects.filter(ativo=True):
            set_current_tenant(tenant)
            a, e = self._processar_tenant(tenant)
            total_alertas += a
            total_escalados += e

        if total_alertas or total_escalados:
            self.stdout.write(self.style.SUCCESS(
                f'SLA: {total_alertas} alertas, {total_escalados} escalados'
            ))

    def _processar_tenant(self, tenant):
        from apps.suporte.models import Ticket, HistoricoTicket

        agora = timezone.now()
        alertas = 0
        escalados = 0

        # Tickets abertos com SLA definido
        tickets = Ticket.objects.filter(
            status__in=['aberto', 'em_andamento', 'aguardando_cliente'],
            sla_horas__isnull=False,
        ).select_related('categoria', 'atendente')

        for ticket in tickets:
            horas_decorridas = (agora - ticket.data_abertura).total_seconds() / 3600
            sla = ticket.sla_horas
            percentual = (horas_decorridas / sla * 100) if sla else 0

            # Ja tem alerta recente? (evitar spam)
            alerta_recente = HistoricoTicket.objects.filter(
                ticket=ticket, tipo='sla',
                data__gte=agora - timedelta(hours=4),
            ).exists()

            if alerta_recente:
                continue

            # SLA estourado (>100%)
            if percentual > 100:
                HistoricoTicket.objects.create(
                    ticket=ticket, tipo='sla',
                    descricao=f'SLA estourado: {horas_decorridas:.1f}h de {sla}h ({percentual:.0f}%)',
                )
                alertas += 1

                # Escalacao: se nao tem atendente ou ja estourou muito
                if not ticket.atendente or percentual > 150:
                    self._escalar_ticket(ticket, percentual)
                    escalados += 1

            # SLA prestes a estourar (>80%)
            elif percentual > 80:
                HistoricoTicket.objects.create(
                    ticket=ticket, tipo='sla',
                    descricao=f'SLA em risco: {horas_decorridas:.1f}h de {sla}h ({percentual:.0f}%)',
                )
                alertas += 1

        return alertas, escalados

    def _escalar_ticket(self, ticket, percentual):
        from apps.suporte.models import HistoricoTicket

        # Aumentar prioridade se nao e urgente
        if ticket.prioridade != 'urgente':
            anterior = ticket.prioridade
            ticket.prioridade = 'urgente'
            ticket.save(update_fields=['prioridade'])
            HistoricoTicket.objects.create(
                ticket=ticket, tipo='escalacao',
                campo='prioridade', valor_anterior=anterior, valor_novo='urgente',
                descricao=f'Escalado automaticamente: SLA em {percentual:.0f}%. Prioridade elevada para urgente.',
            )

        logger.info("Ticket #%s escalado: SLA em %d%%", ticket.numero, percentual)
