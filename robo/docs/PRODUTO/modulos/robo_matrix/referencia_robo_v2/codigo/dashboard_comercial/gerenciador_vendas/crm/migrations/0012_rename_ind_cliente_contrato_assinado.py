"""Renomeia o estágio ind_cliente do pipeline de Indicação para Contrato Assinado."""
from django.db import migrations


def aplicar(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    PipelineEstagio.objects.filter(slug='ind_cliente').update(
        nome='Contrato Assinado',
        icone_fa='fa-file-circle-check',
    )


def reverter(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    PipelineEstagio.objects.filter(slug='ind_cliente').update(
        nome='Cliente Criado',
        icone_fa='fa-id-card',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0011_rename_ind_apto_aguardando_assinatura'),
    ]

    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
