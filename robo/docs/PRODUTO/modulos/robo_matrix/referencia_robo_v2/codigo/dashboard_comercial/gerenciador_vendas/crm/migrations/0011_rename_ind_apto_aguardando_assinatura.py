"""Renomeia o estágio ind_apto do pipeline de Indicação para Aguardando Assinatura."""
from django.db import migrations


def aplicar(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    PipelineEstagio.objects.filter(slug='ind_apto').update(
        nome='Aguardando Assinatura',
        cor_hex='#f59e0b',
        icone_fa='fa-file-signature',
    )


def reverter(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    PipelineEstagio.objects.filter(slug='ind_apto').update(
        nome='Pronto p/ Conversão',
        cor_hex='#0ea5e9',
        icone_fa='fa-user-check',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0010_seed_mensagens_pipeline'),
    ]

    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
