"""
Migration 0003: ajustes no estágio de negociação e seed das tags de qualificação.

Mudanças:
  1. Renomeia o estágio tipo='negociacao' de "Proposta Enviada" para
     "Aguardando Assinatura" e atualiza o slug para 'aguardando_assinatura'.
  2. Cria as TagCRM de qualificação: Comercial, Endereço, Documental.
"""
from django.db import migrations


TAGS_QUALIFICACAO = [
    {'nome': 'Comercial',  'cor_hex': '#667eea'},
    {'nome': 'Endereço',   'cor_hex': '#f39c12'},
    {'nome': 'Documental', 'cor_hex': '#0ea5e9'},
]


def aplicar(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    TagCRM = apps.get_model('crm', 'TagCRM')

    # 1. Atualizar estágio negociacao para "Aguardando Assinatura"
    PipelineEstagio.objects.filter(tipo='negociacao').update(
        nome='Aguardando Assinatura',
        slug='aguardando_assinatura',
        icone_fa='fa-file-signature',
    )

    # 2. Criar tags de qualificação
    for dados in TAGS_QUALIFICACAO:
        TagCRM.objects.get_or_create(
            nome=dados['nome'],
            defaults={'cor_hex': dados['cor_hex']},
        )


def reverter(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    TagCRM = apps.get_model('crm', 'TagCRM')

    PipelineEstagio.objects.filter(tipo='negociacao').update(
        nome='Proposta Enviada',
        slug='proposta',
        icone_fa='fa-file-contract',
    )

    nomes = [t['nome'] for t in TAGS_QUALIFICACAO]
    TagCRM.objects.filter(nome__in=nomes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_seed_estagios'),
    ]

    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
