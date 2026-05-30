"""Dispatcher central. Roda a cada 1min via Easypanel cron service.

Algoritmo:
1. Pega advisory lock (Postgres) pra evitar 2 dispatchers em paralelo.
2. Pra cada CronJob ativo, checa se a expressao `schedule` bate com o minuto atual.
3. Se bater e nao tiver outra execucao no mesmo minuto, dispara via subprocess.
4. Captura stdout/stderr/return_code, cria ExecucaoCron, atualiza CronJob.

Uso:
    python manage.py dispatcher_cron
    python manage.py dispatcher_cron --dry-run   # so lista quem rodaria
"""
import subprocess
import sys
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.cron.models import CronJob, ExecucaoCron
from apps.cron.services import cron_match


LOCK_KEY = 7384921  # qualquer inteiro fixo. So serve pra pg_advisory_lock.


class Command(BaseCommand):
    help = 'Dispara CronJobs ativos cujo schedule bate com o minuto atual.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='So lista quem rodaria, sem disparar nada.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']

        with connection.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s)', [LOCK_KEY])
            locked = cur.fetchone()[0]
        if not locked:
            self.stdout.write(self.style.WARNING('Outro dispatcher esta rodando. Skip.'))
            return

        try:
            self._run(dry)
        finally:
            with connection.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(%s)', [LOCK_KEY])

    def _run(self, dry):
        agora = timezone.now()
        jobs = CronJob.objects.filter(ativo=True)
        candidatos = []
        for job in jobs:
            try:
                if cron_match(job.schedule, agora):
                    inicio_minuto = agora.replace(second=0, microsecond=0)
                    ja_no_minuto = ExecucaoCron.objects.filter(
                        cron_job=job, inicio__gte=inicio_minuto
                    ).exists()
                    if not ja_no_minuto:
                        candidatos.append(job)
            except ValueError as e:
                self.stderr.write(f'[{job.nome}] schedule invalido: {e}')

        marca = ' [DRY]' if dry else ''
        if not candidatos:
            self.stdout.write(f'{agora:%H:%M} nada pra rodar.{marca}')
            return

        self.stdout.write(
            f'{agora:%H:%M} disparando {len(candidatos)} job(s):{marca} '
            + ', '.join(j.nome for j in candidatos)
        )

        if dry:
            return

        for job in candidatos:
            self._dispatch(job, disparado_por='dispatcher')

    def _dispatch(self, job, disparado_por='dispatcher'):
        """Executa um CronJob e registra ExecucaoCron. Reutilizado pelo botao
        'Executar agora' do painel admin (passando disparado_por='manual:<user>')."""
        exec_row = ExecucaoCron.objects.create(
            cron_job=job, status='running', disparado_por=disparado_por,
        )
        CronJob.objects.filter(pk=job.pk).update(last_status='running')

        cmd = [sys.executable, 'manage.py', job.command]
        if job.args.strip():
            cmd.extend(job.args.strip().split())

        t0 = time.monotonic()
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=job.timeout_segundos,
                cwd=str(Path(settings.BASE_DIR)),
            )
            dur = time.monotonic() - t0
            exec_row.status = 'success' if r.returncode == 0 else 'erro'
            exec_row.return_code = r.returncode
            exec_row.stdout = (r.stdout or '')[:10_000]
            exec_row.stderr = (r.stderr or '')[:10_000]
        except subprocess.TimeoutExpired as e:
            dur = time.monotonic() - t0
            exec_row.status = 'timeout'
            partial = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode(errors='replace') if e.stdout else '')
            exec_row.stderr = f'Timeout apos {job.timeout_segundos}s. Stdout parcial:\n{partial[:2000]}'
        except Exception as e:
            dur = time.monotonic() - t0
            exec_row.status = 'erro'
            exec_row.stderr = f'Excecao no dispatcher: {type(e).__name__}: {e}'

        exec_row.fim = timezone.now()
        exec_row.duracao_segundos = round(dur, 3)
        exec_row.save()

        CronJob.objects.filter(pk=job.pk).update(
            last_run_at=exec_row.fim, last_status=exec_row.status
        )
        self.stdout.write(f'  -> {job.nome}: {exec_row.status} em {dur:.2f}s')
        return exec_row
