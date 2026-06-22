"""
Processa a fila da automação (roda periódico, ex: a cada minuto, via apps.cron):
    python manage.py automacao_retomar --settings=gerenciador_vendas.settings

Faz duas coisas:
- `rodar_novos`: roda as execuções ENFILEIRADAS por gatilho (deferido — o evento só
  enfileirou, quem roda o fluxo é aqui, fora do thread do evento).
- `retomar_pendentes`: retoma as execuções PAUSADAS (delay/timeout) que já venceram.
"""
from django.core.management.base import BaseCommand

from apps.automacao.execucao import retomar_pendentes, rodar_novos


class Command(BaseCommand):
    help = 'Processa a fila da automação: roda enfileiradas (gatilho) + retoma pausadas (delay).'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=100)

    def handle(self, *args, **options):
        limite = options['limite']
        novas = rodar_novos(limite=limite)
        retomadas = retomar_pendentes(limite=limite)
        self.stdout.write(self.style.SUCCESS(
            f'enfileiradas rodadas: {novas} · pausadas retomadas: {retomadas}'
        ))
