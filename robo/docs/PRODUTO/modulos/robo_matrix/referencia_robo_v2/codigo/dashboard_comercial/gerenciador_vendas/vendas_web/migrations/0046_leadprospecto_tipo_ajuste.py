"""Adiciona LeadProspecto.tipo_ajuste pro fluxo de revisão pós-negação.

Quando cliente nega dados_confirmados, a API pergunta o que quer ajustar
(endereço, dados pessoais ou plano). A resposta vai pra este campo.

Em seguida, a API limpa os campos correspondentes e zera tipo_ajuste +
dados_confirmados pra re-perguntar.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('vendas_web', '0045_leadprospecto_dados_confirmados'),
    ]
    operations = [
        migrations.AddField(
            model_name='leadprospecto',
            name='tipo_ajuste',
            field=models.CharField(
                max_length=20, blank=True, default='',
                choices=[
                    ('endereco', 'Endereço'),
                    ('dados_pessoais', 'Dados pessoais'),
                    ('plano', 'Plano selecionado'),
                ],
                verbose_name='Tipo de ajuste solicitado',
                help_text='Setado quando cliente nega dados_confirmados e indica o que quer corrigir.',
            ),
        ),
    ]
