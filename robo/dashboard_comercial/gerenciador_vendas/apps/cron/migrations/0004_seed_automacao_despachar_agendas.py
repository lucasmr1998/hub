"""Seed do cron job automacao_despachar_agendas. Idempotente.

Job que despacha as rodadas de varredura da engine de automacao (gatilho
`agenda`). Nasce desligado; ligar somente com os fluxos de varredura prontos.
"""
from django.db import migrations


JOB = {
    'nome': 'automacao_despachar_agendas',
    'command': 'automacao_despachar_agendas',
    'args': '',
    'schedule': '*/5 * * * *',
    'ativo': False,
    'timeout_segundos': 120,
    'descricao': (
        'Despacha as varreduras (gatilho agenda) da engine de automacao. '
        'Ligar somente com os fluxos de varredura prontos.'
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
        ('cron', '0003_seed_automacao_retomar'),
    ]
    operations = [
        migrations.RunPython(seed, reverse),
    ]
