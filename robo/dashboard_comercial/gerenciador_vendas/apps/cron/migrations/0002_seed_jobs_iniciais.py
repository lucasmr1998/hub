"""Seed dos 3 cron jobs iniciais (ativos por default). Idempotente.

- encerrar_inativos: a cada 15min, encerra conversas humanas inativas conforme
  config por tenant (ConfiguracaoInbox.encerramento_auto_ativo).
- processar_pendentes: a cada 30min, envia leads com status_api='pendente'
  pra HubSoft.
- sincronizar_clientes: a cada 1min, espelha clientes/servicos do HubSoft pra
  o banco local.
"""
from django.db import migrations


JOBS = [
    {
        'nome': 'encerrar_inativos',
        'command': 'encerrar_inativos',
        'args': '',
        'schedule': '*/15 * * * *',
        'ativo': True,
        'timeout_segundos': 600,
        'descricao': (
            'Encerra conversas humanas (aberta/pendente) sem mensagem nova '
            'ha N horas. Configuracao por tenant em ConfiguracaoInbox: '
            'encerramento_auto_ativo, encerramento_auto_horas, '
            'encerramento_auto_aviso_ativo, encerramento_auto_aviso_texto. '
            'Bot intacto.'
        ),
    },
    {
        'nome': 'processar_pendentes',
        'command': 'processar_pendentes',
        'args': '',
        'schedule': '*/30 * * * *',
        'ativo': True,
        'timeout_segundos': 1200,
        'descricao': 'Envia leads com status_api=pendente pra HubSoft via API.',
    },
    {
        'nome': 'sincronizar_clientes',
        'command': 'sincronizar_clientes',
        'args': '',
        'schedule': '* * * * *',
        'ativo': True,
        'timeout_segundos': 300,
        'descricao': 'Sincroniza clientes/servicos do HubSoft pro banco local.',
    },
]


def seed(apps, schema_editor):
    CronJob = apps.get_model('cron', 'CronJob')
    for j in JOBS:
        CronJob.objects.update_or_create(
            nome=j['nome'],
            defaults={
                'command': j['command'],
                'args': j['args'],
                'schedule': j['schedule'],
                'ativo': j['ativo'],
                'timeout_segundos': j['timeout_segundos'],
                'descricao': j['descricao'],
            },
        )


def reverse(apps, schema_editor):
    CronJob = apps.get_model('cron', 'CronJob')
    CronJob.objects.filter(nome__in=[j['nome'] for j in JOBS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('cron', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed, reverse),
    ]
