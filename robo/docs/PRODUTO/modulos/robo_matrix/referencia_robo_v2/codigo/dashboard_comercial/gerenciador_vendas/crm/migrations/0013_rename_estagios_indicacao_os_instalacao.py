"""Ajusta nomes dos estágios de indicação: abertura de O.S. e aguardando instalação."""
from django.db import migrations


def aplicar(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    PipelineEstagio.objects.filter(slug='ind_cliente').update(
        nome='Aguardando Abertura de O.S.',
        icone_fa='fa-screwdriver-wrench',
    )
    PipelineEstagio.objects.filter(slug='ind_agendado').update(
        nome='Aguardando Instalação',
        icone_fa='fa-tools',
    )


def reverter(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    PipelineEstagio.objects.filter(slug='ind_cliente').update(
        nome='Contrato Assinado',
        icone_fa='fa-file-circle-check',
    )
    PipelineEstagio.objects.filter(slug='ind_agendado').update(
        nome='Atendimento/O.S. Aberta',
        icone_fa='fa-screwdriver-wrench',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0012_rename_ind_cliente_contrato_assinado'),
    ]

    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
