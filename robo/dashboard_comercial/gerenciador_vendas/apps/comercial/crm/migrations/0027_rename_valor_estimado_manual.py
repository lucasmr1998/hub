"""Renomeia valor_estimado -> valor_estimado_manual (preserva dados).

Faz parte da refatoracao "valor_estimado como property" — o campo persistido
vira override opcional, e o valor exibido eh calculado da soma dos itens.

A migration eh SO o rename. Backfill (criar ItemOportunidade placeholder
pras ops com valor_estimado_manual mas sem itens) acontece numa migration
de dados separada (0028) pra deixar o rollback mais simples.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0026_configuracaocrm_campos_card_padrao_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='oportunidadevenda',
            old_name='valor_estimado',
            new_name='valor_estimado_manual',
        ),
        migrations.AlterField(
            model_name='oportunidadevenda',
            name='valor_estimado_manual',
            field=__import__('django.db.models', fromlist=['DecimalField']).DecimalField(
                max_digits=12, decimal_places=2, null=True, blank=True,
                verbose_name='Valor Estimado Manual (R$)',
                help_text='Override opcional. Se vazio, valor_estimado eh a soma dos itens.',
            ),
        ),
    ]
