"""Adiciona ao LeadProspecto os 3 campos necessários pro fluxo dinâmico de venda:

- tipo_imovel        → regra `tipo_imovel`         (Casa/Empresa)
- turno_instalacao   → regra `escolha_turno`       (Manhã/Tarde)
- data_instalacao    → regra `escolha_data`        (data preferida da instalação)

Esses 3 campos cobrem todas as 22 regras de validação que precisam armazenar
algo no lead. Os demais campos já existem no model.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('vendas_web', '0041_leadprospecto_data_ultima_tentativa_sync_hubsoft'),
    ]

    operations = [
        migrations.AddField(
            model_name='leadprospecto',
            name='tipo_imovel',
            field=models.CharField(
                blank=True,
                max_length=20,
                choices=[
                    ('casa', 'Casa / Residencial'),
                    ('empresa', 'Empresa / Comercial'),
                ],
                verbose_name='Tipo do imóvel',
                help_text='Coletado pela regra `tipo_imovel` no fluxo de vendas',
            ),
        ),
        migrations.AddField(
            model_name='leadprospecto',
            name='turno_instalacao',
            field=models.CharField(
                blank=True,
                max_length=10,
                choices=[
                    ('manha', 'Manhã'),
                    ('tarde', 'Tarde'),
                ],
                verbose_name='Turno de instalação',
                help_text='Coletado pela regra `escolha_turno`',
            ),
        ),
        migrations.AddField(
            model_name='leadprospecto',
            name='data_instalacao',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='Data de instalação',
                help_text='Coletado pela regra `escolha_data` (data escolhida pelo cliente)',
            ),
        ),
    ]
