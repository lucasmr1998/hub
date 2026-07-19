"""Debug: processa UM registro escolhendo processo/executor/dry-run.

    manage.py hubsoft_processar_um --processo novo_servico --id 12 --executor webdriver --dry-run

Não marca a fila (não grava hubsoft_processado_*) — é só para validar o executor.
Use os workers (hubsoft_poll_*) para o processamento real da fila.
"""
from django.core.management.base import BaseCommand

from posvenda_hubsoft.executores.seletor import processar


class Command(BaseCommand):
    help = 'Executa um único registro (debug) escolhendo processo/executor/dry-run'

    def add_arguments(self, parser):
        parser.add_argument('--processo', required=True,
                            choices=['novo_servico', 'upgrade', 'conversao'])
        parser.add_argument('--id', type=int, required=True)
        parser.add_argument('--executor', choices=['webdriver', 'api_interna'],
                            help='força um executor (sem fallback)')
        parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                            help='não salva no HubSoft (default já é forçado pelo guard)')
        parser.add_argument('--com-janela', dest='com_janela', action='store_true',
                            help='webdriver com janela (default headless)')

    def handle(self, *args, **o):
        kw = {}
        if o['processo'] in ('novo_servico',):
            kw['headless'] = not o['com_janela']
        res = processar(
            o['processo'], o['id'], dry_run=o['dry_run'],
            executor_forcado=o.get('executor'), **kw,
        )
        cor = self.style.SUCCESS if res.status in ('sucesso', 'dry_run') else self.style.ERROR
        self.stdout.write(cor(f'status={res.status} executor={res.executor} '
                              f'etapa={res.etapa} dur={res.duracao_ms}ms'))
        if res.erro:
            self.stdout.write(self.style.WARNING(f'erro: {res.erro}'))
        if res.metadados:
            self.stdout.write(f'metadados: {res.metadados}')
