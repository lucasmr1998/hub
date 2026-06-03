"""Signals do cron — dispara alerta quando ExecucaoCron falha.

Tarefa Workspace #152.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.cron.models import ExecucaoCron

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ExecucaoCron)
def alertar_quando_cron_falha(sender, instance: ExecucaoCron, created, **kwargs):
    """Quando ExecucaoCron termina com status='error', dispara alerta."""
    # Roda so quando o execucao FECHA (status muda de running pra error)
    if instance.status != 'error':
        return
    if not instance.fim:
        return  # ainda esta correndo

    try:
        from apps.sistema.services_alertas import disparar_alerta
        job = instance.cron_job
        rc = instance.return_code if instance.return_code is not None else '?'
        stderr_snippet = (instance.stderr or '')[:600]
        stdout_snippet = (instance.stdout or '')[:400]

        disparar_alerta(
            tipo='cron_falhou',
            titulo=f'CronJob "{job.nome}" falhou (rc={rc})',
            mensagem=(
                f'Comando: manage.py {job.command} {job.args or ""}\n'
                f'Schedule: {job.schedule}\n'
                f'Inicio: {instance.inicio}\n'
                f'Duracao: {instance.duracao_segundos}s\n\n'
                f'STDERR: {stderr_snippet}\n\n'
                f'STDOUT: {stdout_snippet}'
            ),
            dedup_key=f'cron_falhou:{job.nome}',
            dados_extras={
                'cron_job_id': job.id,
                'execucao_id': instance.id,
                'return_code': instance.return_code,
            },
        )
    except Exception as exc:
        logger.error('[alertas] falha ao processar signal de cron error: %s', exc)
