"""Adiciona LeadProspecto.data_primeira_tentativa_sync_hubsoft.

Permite distinguir entre 'primeira tentativa' (janela de grace 15min sem
backoff) e 'tentativas seguintes' (backoff de 6h depois da janela).
"""
from django.db import migrations, models
from django.db.models import F


def backfill_primeira_tentativa(apps, schema_editor):
    """Pra leads que já tinham data_ultima_tentativa, considera essa data
    como a 1ª tentativa também — assim a janela de grace já é considerada
    expirada (não vai abrir uma janela nova de 15min após o deploy).
    """
    LeadProspecto = apps.get_model('vendas_web', 'LeadProspecto')
    LeadProspecto.objects.filter(
        data_ultima_tentativa_sync_hubsoft__isnull=False,
        data_primeira_tentativa_sync_hubsoft__isnull=True,
    ).update(data_primeira_tentativa_sync_hubsoft=F('data_ultima_tentativa_sync_hubsoft'))


def reverter(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('vendas_web', '0047_docs_nullable'),
    ]
    operations = [
        migrations.AddField(
            model_name='leadprospecto',
            name='data_primeira_tentativa_sync_hubsoft',
            field=models.DateTimeField(
                null=True, blank=True,
                verbose_name='Primeira tentativa de sync Hubsoft',
                help_text='Set apenas na 1ª tentativa.',
            ),
        ),
        migrations.RunPython(backfill_primeira_tentativa, reverter),
    ]
