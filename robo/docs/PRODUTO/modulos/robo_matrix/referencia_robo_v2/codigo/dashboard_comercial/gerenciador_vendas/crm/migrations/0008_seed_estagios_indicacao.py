"""Semeia os estágios do pipeline de INDICAÇÕES (operado por pessoas).

Fluxo 100% manual: operador cadastra a indicação → completa os dados → quando
aptos, o lead vira prospecto → cliente → operador abre atendimento + O.S. pela
ferramenta. Sem docs por IA / contrato automático. Espelha o padrão da 0006.
"""
from django.db import migrations


ESTAGIOS_INDICACAO = [
    # (slug, nome, ordem, cor, icone, prob, ganho, perdido)
    ('ind_recebida',  'Indicação Recebida',      1, '#8b5cf6', 'fa-lightbulb',          10, False, False),
    ('ind_dados',     'Completando Dados',       2, '#6366f1', 'fa-clipboard-list',     30, False, False),
    ('ind_apto',      'Aguardando Assinatura',   3, '#f59e0b', 'fa-file-signature',     50, False, False),
    ('ind_cliente',   'Aguardando Abertura de O.S.', 4, '#0d6efd', 'fa-screwdriver-wrench', 75, False, False),
    ('ind_agendado',  'Aguardando Instalação',       5, '#fd7e14', 'fa-tools',              90, False, False),
    ('ind_concluido', 'Concluído',               6, '#198754', 'fa-check-circle',      100, True,  False),
    ('ind_perdido',   'Perdido',                 7, '#dc3545', 'fa-times-circle',        0, False, True),
]


def aplicar(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    for (slug, nome, ordem, cor, icone, prob, ganho, perdido) in ESTAGIOS_INDICACAO:
        PipelineEstagio.objects.update_or_create(
            slug=slug,
            defaults={
                'nome': nome,
                'pipeline_tipo': 'indicacao',
                'ordem': ordem,
                'cor_hex': cor,
                'icone_fa': icone,
                'tipo': 'novo',
                'probabilidade_padrao': prob,
                'is_final_ganho': ganho,
                'is_final_perdido': perdido,
                'ativo': True,
            },
        )


def reverter(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    slugs = [e[0] for e in ESTAGIOS_INDICACAO]
    PipelineEstagio.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('crm', '0007_alter_oportunidadevenda_tipo_and_more'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
