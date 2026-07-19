"""Adiciona o pipeline 'wifeed' aos choices (espelha a 0007 da indicação)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0013_rename_estagios_indicacao_os_instalacao'),
    ]

    operations = [
        migrations.AlterField(
            model_name='oportunidadevenda',
            name='tipo',
            field=models.CharField(choices=[('aquisicao', 'Aquisição'), ('novo_servico', 'Novo Serviço'), ('upgrade', 'Upgrade de Plano'), ('atendimento', 'Atendimento'), ('indicacao', 'Indicação'), ('wifeed', 'Wifeed')], db_index=True, default='aquisicao', max_length=20, verbose_name='Tipo / Pipeline'),
        ),
        migrations.AlterField(
            model_name='pipelineestagio',
            name='pipeline_tipo',
            field=models.CharField(choices=[('aquisicao', 'Aquisição (lead novo → cliente)'), ('novo_servico', 'Novo Serviço (cliente existente)'), ('upgrade', 'Upgrade de Plano'), ('atendimento', 'Atendimento / Suporte'), ('indicacao', 'Indicação (operado por pessoas)'), ('wifeed', 'Wifeed (portal WiFi)')], db_index=True, default='aquisicao', max_length=20, verbose_name='Pipeline'),
        ),
    ]
