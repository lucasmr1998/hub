"""Adiciona LeadProspecto.dados_confirmados pra confirmação final pré-assinatura.

Antes de perguntar turno/data de instalação, o flow mostra TODOS os dados
coletados (plano, dados pessoais, endereço) e pede confirmação:

- True  → cliente confirmou, segue pro agendamento de instalação
- False → cliente negou (algo está errado), flow transborda pra atendente
- None  → ainda não perguntou (estado inicial)
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('vendas_web', '0044_leadprospecto_docs_recebidos'),
    ]
    operations = [
        migrations.AddField(
            model_name='leadprospecto',
            name='dados_confirmados',
            field=models.BooleanField(
                null=True, blank=True,
                verbose_name='Dados finais confirmados pelo cliente',
                help_text='True=confirmou tudo (ok pra contratar); False=negou (transbordo); None=ainda não perguntou',
            ),
        ),
    ]
