"""Adiciona 'wifeed' aos choices de origem/canal_entrada do LeadProspecto."""
from django.db import migrations, models


ORIGEM_CHOICES = [
    ('site', 'Site'),
    ('facebook', 'Facebook'),
    ('instagram', 'Instagram'),
    ('google', 'Google Ads'),
    ('whatsapp', 'WhatsApp'),
    ('indicacao', 'Indicação'),
    ('wifeed', 'Wifeed'),
    ('telefone', 'Telefone'),
    ('email', 'Email'),
    ('outros', 'Outros'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('vendas_web', '0067_leadprospecto_nome_confirmado'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leadprospecto',
            name='origem',
            field=models.CharField(choices=ORIGEM_CHOICES, default='site', help_text='Canal de origem do lead', max_length=50, verbose_name='Origem'),
        ),
        migrations.AlterField(
            model_name='leadprospecto',
            name='canal_entrada',
            field=models.CharField(blank=True, choices=ORIGEM_CHOICES, help_text='Canal por onde o lead entrou no sistema', max_length=50, null=True, verbose_name='Canal de Entrada'),
        ),
    ]
