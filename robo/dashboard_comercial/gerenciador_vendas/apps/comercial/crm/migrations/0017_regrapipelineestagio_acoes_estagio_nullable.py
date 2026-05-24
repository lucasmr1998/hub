from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0016_venda'),
    ]

    operations = [
        migrations.AlterField(
            model_name='regrapipelineestagio',
            name='estagio',
            field=models.ForeignKey(
                blank=True,
                help_text='Estágio para onde a oportunidade será movida. Deixe em branco para regras de ação sem movimento de estágio.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='regras',
                to='crm.pipelineestagio',
                verbose_name='Estágio destino',
            ),
        ),
        migrations.AddField(
            model_name='regrapipelineestagio',
            name='acoes',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Ações executadas quando a regra dispara: [{tipo: 'criar_venda'}, ...]",
                verbose_name='Ações adicionais',
            ),
        ),
    ]
