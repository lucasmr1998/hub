"""Reconcilia oportunidades de INDICAÇÃO com agendamento e status HubSoft.

    python manage.py crm_sincronizar_indicacao
"""
from django.core.management.base import BaseCommand

from crm.services.indicacao_pipeline import sincronizar_indicacao_pendentes


class Command(BaseCommand):
    help = 'Sincroniza pipeline de Indicação (contrato, O.S., serviço habilitado).'

    def handle(self, *args, **opts):
        sincronizar_indicacao_pendentes()
        self.stdout.write(self.style.SUCCESS('Indicação sincronizada.'))
