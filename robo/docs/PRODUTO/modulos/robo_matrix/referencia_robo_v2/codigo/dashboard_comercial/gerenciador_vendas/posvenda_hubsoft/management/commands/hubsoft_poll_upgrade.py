"""Worker: processa a fila de UPGRADE DE PLANO no HubSoft (robovendas_v2).

Pega UpgradePlano finalizado e não processado, executa (webdriver "Migrar para
Outro Serviço"), grava o resultado. Advisory lock 947_312_006. O CRM (up_*) é
movido por posvenda_sync / crm_reconciliar_posvenda.

    manage.py hubsoft_poll_upgrade --intervalo 60 --batch 2 [--dry-run] [--once]
"""
import signal
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from posvenda_hubsoft.executores.seletor import processar

ADVISORY_LOCK = 947_312_006


class Command(BaseCommand):
    help = 'Worker da fila de upgrade de plano (HubSoft) — robovendas_v2'

    def add_arguments(self, parser):
        parser.add_argument('--intervalo', type=int, default=60)
        parser.add_argument('--batch', type=int, default=2)
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **o):
        self._parar = False
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, '_parar', True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, '_parar', True))
        self.stdout.write(self.style.SUCCESS(
            f'[upgrade] worker iniciado (batch={o["batch"]} dry_run={o["dry_run"]})'))
        while not self._parar:
            try:
                n = self._ciclo(o['batch'], o['dry_run'])
                if n:
                    self.stdout.write(f'[upgrade] ciclo processou {n}')
            except Exception as e:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f'[upgrade] erro no ciclo: {e}'))
                # Conexão de DB pode ter morrido (queda de rede/restart do
                # Postgres). Fecha TODAS — o Django reabre na próxima query.
                # Sem isso o worker fica preso em "connection already closed".
                try:
                    from django.db import connections
                    connections.close_all()
                except Exception:  # noqa: BLE001
                    pass
            if o['once']:
                break
            for _ in range(o['intervalo']):
                if self._parar:
                    break
                time.sleep(1)
        self.stdout.write('[upgrade] worker encerrado')

    def _ciclo(self, batch, dry_run):
        from vendas_web.models import UpgradePlano
        with connection.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s)', [ADVISORY_LOCK])
            if not cur.fetchone()[0]:
                return 0
        try:
            pendentes = list(
                UpgradePlano.objects.filter(
                    status='finalizado', hubsoft_processado_em__isnull=True,
                ).order_by('finalizado_em', 'id').values_list('id', flat=True)[:batch]
            )
            for up_id in pendentes:
                if self._parar:
                    break
                self._processar_um(up_id, dry_run)
            return len(pendentes)
        finally:
            with connection.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(%s)', [ADVISORY_LOCK])

    def _processar_um(self, up_id, dry_run):
        from vendas_web.models import UpgradePlano
        res = processar('upgrade', up_id, dry_run=dry_run)
        status_fila = {'sucesso': 'sucesso', 'dry_run': 'dry_run', 'falha': 'falha'}.get(
            res.status, 'falha')
        with transaction.atomic():
            up = UpgradePlano.objects.select_for_update().get(pk=up_id)
            up.hubsoft_processado_em = timezone.now()
            up.hubsoft_processado_status = status_fila
            up.hubsoft_erro = res.erro or ''
            up.save(update_fields=['hubsoft_processado_em', 'hubsoft_processado_status',
                                   'hubsoft_erro', 'atualizado_em'])
        self.stdout.write(
            f'[upgrade] up={up_id} → {res.status} ({res.executor}, {res.duracao_ms}ms)')
