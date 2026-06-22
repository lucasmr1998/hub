"""
Retoma execuções de automação pausadas (delay) cujo agendamento já venceu.

Roda periódico (ex: a cada minuto) via crontab / apps.cron:
    python manage.py automacao_retomar --settings=gerenciador_vendas.settings
"""
from django.core.management.base import BaseCommand

from apps.automacao.execucao import retomar_pendentes


class Command(BaseCommand):
    help = 'Retoma execuções de automação pausadas (delay) que já venceram.'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=100)

    def handle(self, *args, **options):
        n = retomar_pendentes(limite=options['limite'])
        self.stdout.write(self.style.SUCCESS(f'execuções retomadas: {n}'))
