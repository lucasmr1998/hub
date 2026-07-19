from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vendas_web', '0061_perfilacesso'),
    ]

    operations = [
        migrations.AddField(
            model_name='cidadeviabilidade',
            name='regional',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=30,
                db_index=True,
                help_text='Regional responsável pelo atendimento desta cidade (ex: REGIONAL - 01)',
                verbose_name='Regional',
            ),
        ),
        migrations.AddIndex(
            model_name='cidadeviabilidade',
            index=models.Index(fields=['regional'], name='vendas_web__regiona_f322d6_idx'),
        ),
    ]
