"""Seed do cron job automacao_retomar. Idempotente.

Job para gerenciar a fila de execucoes enfileiradas e retomar automacoes
pausadas. Nasce desligado e sera ativado manualmente no cutover da engine.
"""
from django.db import migrations


JOB = {
    'nome': 'automacao_retomar',
    'command': 'automacao_retomar',
    'args': '',
    'schedule': '* * * * *',
    'ativo': False,
    'timeout_segundos': 300,
    'descricao': (
        'Fila da engine de automacao: roda execucoes enfileiradas + retoma '
        'pausadas. Ligar somente no cutover.'
    ),
}


def seed(apps, schema_editor):
    CronJob = apps.get_model('cron', 'CronJob')
    CronJob.objects.update_or_create(
        nome=JOB['nome'],
        defaults={
            'command': JOB['command'],
            'args': JOB['args'],
            'schedule': JOB['schedule'],
            'ativo': JOB['ativo'],
            'timeout_segundos': JOB['timeout_segundos'],
            'descricao': JOB['descricao'],
        },
    )


def reverse(apps, schema_editor):
    CronJob = apps.get_model('cron', 'CronJob')
    CronJob.objects.filter(nome=JOB['nome']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('cron', '0002_seed_jobs_iniciais'),
    ]
    operations = [
        migrations.RunPython(seed, reverse),
    ]
