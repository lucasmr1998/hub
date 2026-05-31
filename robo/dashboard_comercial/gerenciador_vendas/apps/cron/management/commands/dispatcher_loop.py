"""Loop infinito que dispara `dispatcher_cron` a cada N segundos.

Roda como **processo em background** dentro do container do `hub` (subido pelo
`entrypoint.sh` antes do daphne). Cada iteracao chama `dispatcher_cron` (que
ja tem advisory lock e idempotencia no mesmo minuto). Se uma iteracao falhar,
loga o erro e segue pro proximo tick — nao morre.

Por que rodar dentro do container do hub em vez de um service Easypanel
separado: simplicidade operacional (1 service, 1 deploy, 1 conjunto de env
vars). O advisory lock no `dispatcher_cron` ja protege contra duplicacao
caso o hub tenha multiplas replicas no futuro.

Uso (dentro do entrypoint.sh):
    python manage.py dispatcher_loop &

Local (dev): roda em foreground:
    python manage.py dispatcher_loop --settings=gerenciador_vendas.settings_local
"""
import logging
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand


logger = logging.getLogger('cron.dispatcher_loop')


class Command(BaseCommand):
    help = 'Loop infinito: chama dispatcher_cron a cada N segundos.'

    def add_arguments(self, parser):
        parser.add_argument('--intervalo', type=int, default=60,
                            help='Segundos entre ticks (default 60).')

    def handle(self, *args, **opts):
        intervalo = opts['intervalo']
        self.stdout.write(self.style.SUCCESS(
            f'[dispatcher_loop] iniciando, intervalo={intervalo}s'
        ))
        # flush imediato pra o log do container mostrar a linha de partida
        self.stdout.flush()

        while True:
            t0 = time.monotonic()
            try:
                call_command('dispatcher_cron')
            except Exception:
                logger.exception('[dispatcher_loop] dispatcher_cron falhou nesta iteracao')
            dur = time.monotonic() - t0
            wait = max(1.0, intervalo - dur)
            time.sleep(wait)
