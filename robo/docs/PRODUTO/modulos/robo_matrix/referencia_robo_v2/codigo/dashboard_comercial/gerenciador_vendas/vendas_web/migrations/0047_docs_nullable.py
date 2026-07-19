"""Torna doc_*_recebida nullable e converte False → None nos leads existentes.

Antes os 3 campos de doc eram BooleanField(default=False). Isso fazia o loop
de coleta no /ia/proximo-passo pular eles (False é tratado como 'já respondido'
pra preservar a semântica de endereco_confirmado=False).

Mudança: docs viram null=True, default=None. None = 'ainda não solicitado',
True = 'upload feito'. Leads existentes com False (que nunca subiram doc)
viram None pra entrarem na sequência de documentação.
"""
from django.db import migrations, models


def false_para_none(apps, schema_editor):
    LeadProspecto = apps.get_model('vendas_web', 'LeadProspecto')
    LeadProspecto.objects.filter(doc_selfie_recebida=False).update(doc_selfie_recebida=None)
    LeadProspecto.objects.filter(doc_frente_recebida=False).update(doc_frente_recebida=None)
    LeadProspecto.objects.filter(doc_verso_recebida=False).update(doc_verso_recebida=None)


def reverter(apps, schema_editor):
    LeadProspecto = apps.get_model('vendas_web', 'LeadProspecto')
    LeadProspecto.objects.filter(doc_selfie_recebida__isnull=True).update(doc_selfie_recebida=False)
    LeadProspecto.objects.filter(doc_frente_recebida__isnull=True).update(doc_frente_recebida=False)
    LeadProspecto.objects.filter(doc_verso_recebida__isnull=True).update(doc_verso_recebida=False)


class Migration(migrations.Migration):
    dependencies = [
        ('vendas_web', '0046_leadprospecto_tipo_ajuste'),
    ]
    operations = [
        migrations.AlterField(
            model_name='leadprospecto',
            name='doc_selfie_recebida',
            field=models.BooleanField(
                null=True, blank=True, default=None,
                verbose_name='Selfie com documento recebida',
                help_text='True=upload feito; None=ainda não solicitado',
            ),
        ),
        migrations.AlterField(
            model_name='leadprospecto',
            name='doc_frente_recebida',
            field=models.BooleanField(
                null=True, blank=True, default=None,
                verbose_name='Frente do documento recebida',
                help_text='True=upload feito; None=ainda não solicitado',
            ),
        ),
        migrations.AlterField(
            model_name='leadprospecto',
            name='doc_verso_recebida',
            field=models.BooleanField(
                null=True, blank=True, default=None,
                verbose_name='Verso do documento recebida',
                help_text='True=upload feito; None=ainda não solicitado',
            ),
        ),
        migrations.RunPython(false_para_none, reverter),
    ]
