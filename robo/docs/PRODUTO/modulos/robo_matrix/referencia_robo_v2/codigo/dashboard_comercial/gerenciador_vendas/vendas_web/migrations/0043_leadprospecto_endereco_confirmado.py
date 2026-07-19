"""Adiciona LeadProspecto.endereco_confirmado para o fluxo de confirmação pós-CEP.

Quando o cliente informa o CEP, o ViaCEP preenche rua/bairro/cidade automaticamente.
Antes de prosseguir, o flow pergunta "Está correto?" e armazena a resposta:

- True  → cliente confirmou, fluxo prossegue pro número da residência
- False → cliente negou, engine limpa rua/bairro/cidade do lead e a sequência
          pede esses campos manualmente um a um
- None  → ainda não perguntou (estado inicial)
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('vendas_web', '0042_leadprospecto_campos_fluxo_dinamico'),
    ]
    operations = [
        migrations.AddField(
            model_name='leadprospecto',
            name='endereco_confirmado',
            field=models.BooleanField(
                null=True, blank=True,
                verbose_name='Endereço confirmado pelo cliente',
                help_text='True=confirmou os dados do ViaCEP; False=negou (precisa preencher manualmente); None=ainda não perguntou',
            ),
        ),
    ]
