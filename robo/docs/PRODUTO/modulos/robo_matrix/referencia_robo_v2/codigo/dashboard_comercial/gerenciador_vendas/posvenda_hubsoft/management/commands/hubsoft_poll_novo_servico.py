"""Worker: processa a fila de NOVO SERVIÇO no HubSoft (robovendas_v2).

Loop: pega NewService finalizado e ainda não processado, executa (webdriver/API
com fallback), grava o resultado em `hubsoft_processado_*`. Advisory lock
947_312_005 (mesmo dos pollings de produção) garante instância única.

    manage.py hubsoft_poll_novo_servico --intervalo 60 --batch 3 [--dry-run] [--once]

Por padrão roda com o guard de dry-run do settings (HUBSOFT_DRY_RUN_FORCADO).
O CRM é movido pelo `crm_reconciliar_posvenda` (rodar em paralelo/timer).
"""
import signal
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from posvenda_hubsoft.executores.seletor import processar

ADVISORY_LOCK = 947_312_005


class Command(BaseCommand):
    help = 'Worker da fila de novo serviço (HubSoft) — robovendas_v2'

    def add_arguments(self, parser):
        parser.add_argument('--intervalo', type=int, default=60)
        parser.add_argument('--batch', type=int, default=3)
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')
        parser.add_argument('--once', action='store_true', help='roda 1 ciclo e sai')

    def handle(self, *args, **o):
        self._parar = False
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, '_parar', True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, '_parar', True))
        self.stdout.write(self.style.SUCCESS(
            f'[novo_servico] worker iniciado (batch={o["batch"]} '
            f'intervalo={o["intervalo"]}s dry_run={o["dry_run"]})'))
        while not self._parar:
            try:
                n = self._ciclo(o['batch'], o['dry_run'])
                if n:
                    self.stdout.write(f'[novo_servico] ciclo processou {n}')
            except Exception as e:  # noqa: BLE001 — worker não pode morrer
                self.stderr.write(self.style.ERROR(f'[novo_servico] erro no ciclo: {e}'))
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
        self.stdout.write('[novo_servico] worker encerrado')

    def _ciclo(self, batch, dry_run):
        from vendas_web.models import NewService
        with connection.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s)', [ADVISORY_LOCK])
            if not cur.fetchone()[0]:
                self.stdout.write('[novo_servico] outra instância tem o lock — pulo')
                return 0
        try:
            pendentes = list(
                NewService.objects.filter(
                    status='finalizado', hubsoft_processado_em__isnull=True,
                ).order_by('finalizado_em', 'id').values_list('id', flat=True)[:batch]
            )
            for ns_id in pendentes:
                if self._parar:
                    break
                self._processar_um(ns_id, dry_run)
            return len(pendentes)
        finally:
            with connection.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(%s)', [ADVISORY_LOCK])

    def _processar_um(self, ns_id, dry_run):
        from vendas_web.models import NewService
        res = processar('novo_servico', ns_id, dry_run=dry_run)
        status_fila = {'sucesso': 'sucesso', 'dry_run': 'dry_run', 'falha': 'falha'}.get(
            res.status, 'falha')
        with transaction.atomic():
            ns = NewService.objects.select_for_update().get(pk=ns_id)
            ns.hubsoft_processado_em = timezone.now()
            ns.hubsoft_processado_status = status_fila
            ns.hubsoft_erro = res.erro or ''
            ns.save(update_fields=['hubsoft_processado_em', 'hubsoft_processado_status',
                                   'hubsoft_erro', 'atualizado_em'])
        self.stdout.write(
            f'[novo_servico] ns={ns_id} → {res.status} ({res.executor}, {res.duracao_ms}ms)')

        # Serviço criado de verdade → abre atendimento + OS no Matrix (que faz
        # o sync do cliente e casa o serviço novo). O CRM avança via posvenda_sync.
        if res.status == 'sucesso':
            try:
                from integracoes.services.agendamento_new_service import (
                    executar_agendamento_new_service)
                r = executar_agendamento_new_service(NewService.objects.get(pk=ns_id))
                self.stdout.write(f'[novo_servico] ns={ns_id} Matrix → {r}')
            except Exception as e:  # noqa: BLE001
                self.stderr.write(self.style.WARNING(
                    f'[novo_servico] ns={ns_id} Matrix falhou (worker periódico tenta de novo): {e}'))
