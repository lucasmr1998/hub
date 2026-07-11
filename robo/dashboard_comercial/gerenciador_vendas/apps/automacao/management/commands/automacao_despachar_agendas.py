"""
Despacha as rodadas de varredura da automação (gatilho `agenda`), roda periódico
via apps.cron:
    python manage.py automacao_despachar_agendas --settings=gerenciador_vendas.settings

Pra cada `Fluxo` ativo com um nó `agenda` configurado e o intervalo já vencido,
dispara (no máximo) 1 rodada — cada item encontrado pela varredura vira UMA
execução enfileirada (`ExecucaoFluxo` status `pendente`, quem roda é o
`automacao_retomar`).
"""
from django.core.management.base import BaseCommand

from apps.automacao.gatilhos import despachar_agendas


class Command(BaseCommand):
    help = 'Despacha as rodadas de varredura da automação (gatilho agenda).'

    def handle(self, *args, **options):
        total = despachar_agendas()
        self.stdout.write(self.style.SUCCESS(f'execuções enfileiradas: {total}'))
