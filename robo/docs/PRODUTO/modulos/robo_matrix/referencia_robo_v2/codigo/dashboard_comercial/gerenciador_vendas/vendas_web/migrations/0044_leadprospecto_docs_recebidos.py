"""Adiciona 3 booleans pra rastrear quais documentos já foram recebidos.

A imagem em si é salva em ImagemLeadProspecto (tabela própria). Os booleans
aqui servem como cache rápido pra a sequência dinâmica saber se a etapa
já foi cumprida — sem precisar fazer JOIN em ImagemLeadProspecto a cada
chamada de /proximo-passo.

- doc_selfie_recebida   → regra documentacao_selfie     (descricao_imagem='selfie_com_doc')
- doc_frente_recebida   → regra documentacao_frente_doc (descricao_imagem='frente_doc')
- doc_verso_recebida    → regra documentacao_verso_doc  (descricao_imagem='verso_doc')
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('vendas_web', '0043_leadprospecto_endereco_confirmado'),
    ]
    operations = [
        migrations.AddField(
            model_name='leadprospecto',
            name='doc_selfie_recebida',
            field=models.BooleanField(
                default=False,
                verbose_name='Selfie com documento recebida',
            ),
        ),
        migrations.AddField(
            model_name='leadprospecto',
            name='doc_frente_recebida',
            field=models.BooleanField(
                default=False,
                verbose_name='Frente do documento recebida',
            ),
        ),
        migrations.AddField(
            model_name='leadprospecto',
            name='doc_verso_recebida',
            field=models.BooleanField(
                default=False,
                verbose_name='Verso do documento recebida',
            ),
        ),
    ]
