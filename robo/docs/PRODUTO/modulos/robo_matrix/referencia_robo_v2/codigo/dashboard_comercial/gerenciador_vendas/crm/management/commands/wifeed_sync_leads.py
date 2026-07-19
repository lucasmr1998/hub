"""Poller: puxa leads das fontes Wifeed ativas (painel) para o pipeline Wifeed.

O núcleo vive em crm.services.wifeed_sync (reutilizado pelo botão "Salvar seleção").
O intervalo do daemon é lido do painel (WifeedConfig.intervalo_minutos) a cada ciclo.

    manage.py wifeed_sync_leads                 # daemon (intervalo do painel)
    manage.py wifeed_sync_leads --once          # um ciclo e sai
    manage.py wifeed_sync_leads --once --dias 3 # backfill dos últimos 3 dias
    manage.py wifeed_sync_leads --once --dry-run
    manage.py wifeed_sync_leads --once --todos-locais
"""
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = 'Puxa leads das fontes Wifeed ativas para o pipeline Wifeed do CRM.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Roda um ciclo e sai.')
        parser.add_argument('--dias', type=int, default=0,
                            help='Além de hoje, quantos dias para trás varrer (backfill).')
        parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                            help='Não grava nada; só loga o que faria.')
        parser.add_argument('--todos-locais', dest='todos_locais', action='store_true',
                            help='Ignora a seleção do painel e puxa TODOS os locais (muito volume).')
        parser.add_argument('--intervalo', type=int, default=None,
                            help='Sobrescreve o intervalo (segundos). Padrão: painel (WifeedConfig).')

    def handle(self, *args, **o):
        if not getattr(settings, 'WIFEED_ENABLED', False):
            self.stdout.write(self.style.WARNING(
                '[wifeed] WIFEED_ENABLED=false — poller desativado. Nada a fazer.'))
            return

        emit = lambda m: self.stdout.write(f'[wifeed] {m}')  # noqa: E731

        if o['once']:
            self._ciclo(o['dias'], o['dry_run'], o['todos_locais'], emit)
            return

        self._parar = False
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, '_parar', True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, '_parar', True))
        self.stdout.write(self.style.SUCCESS('[wifeed] daemon iniciado.'))
        while not self._parar:
            self._ciclo(o['dias'], o['dry_run'], o['todos_locais'], emit)
            for _ in range(self._intervalo_segundos(o['intervalo'])):
                if self._parar:
                    break
                time.sleep(1)
        self.stdout.write(self.style.SUCCESS('[wifeed] encerrado.'))

    def _intervalo_segundos(self, override):
        if override:
            return max(30, override)
        try:
            from crm.models import WifeedConfig
            return max(60, WifeedConfig.get().intervalo_minutos * 60)
        except Exception:  # noqa: BLE001
            return 900

    def _ciclo(self, dias, dry_run, todos_locais, emit):
        try:
            from crm.services.wifeed_sync import sincronizar_leads
            res = sincronizar_leads(dias=dias, dry_run=dry_run,
                                    todos_locais=todos_locais, emit=emit)
            if res.get('erro'):
                self.stdout.write(self.style.WARNING(f'[wifeed] {res["erro"]}'))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'[wifeed] ciclo: criados={res["criados"]} dedupe={res["dedupe"]} '
                    f'ignorados={res["ignorados"]} erros={res["erros"]}'))
        except Exception as e:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f'[wifeed] erro no ciclo: {e}'))
            try:
                connections.close_all()
            except Exception:  # noqa: BLE001
                pass
