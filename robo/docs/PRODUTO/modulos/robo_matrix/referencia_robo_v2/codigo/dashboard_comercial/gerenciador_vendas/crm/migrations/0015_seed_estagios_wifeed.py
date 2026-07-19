"""Semeia os estágios do pipeline WIFEED (leads do portal WiFi).

Mesmo processo do pipeline de Indicação (operado por pessoas: completar dados →
converter em cliente → aguardar contrato → abrir atendimento/O.S. → instalação),
porém pipeline próprio, com entrada automática via poller da API Wifeed.
Espelha o padrão da 0008.
"""
from django.db import migrations


ESTAGIOS_WIFEED = [
    # (slug, nome, ordem, cor, icone, prob, ganho, perdido)
    ('wf_recebida',  'Lead Wifeed Recebido',        1, '#06b6d4', 'fa-wifi',               10, False, False),
    ('wf_dados',     'Completando Dados',           2, '#6366f1', 'fa-clipboard-list',     30, False, False),
    ('wf_apto',      'Aguardando Assinatura',       3, '#f59e0b', 'fa-file-signature',     50, False, False),
    ('wf_cliente',   'Aguardando Abertura de O.S.', 4, '#0d6efd', 'fa-screwdriver-wrench', 75, False, False),
    ('wf_agendado',  'Aguardando Instalação',       5, '#fd7e14', 'fa-tools',              90, False, False),
    ('wf_concluido', 'Concluído',                   6, '#16a34a', 'fa-check-circle',      100, True,  False),
    ('wf_perdido',   'Perdido',                     7, '#dc3545', 'fa-times-circle',        0, False, True),
]


def aplicar(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    for (slug, nome, ordem, cor, icone, prob, ganho, perdido) in ESTAGIOS_WIFEED:
        PipelineEstagio.objects.update_or_create(
            slug=slug,
            defaults={
                'nome': nome,
                'pipeline_tipo': 'wifeed',
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
    slugs = [e[0] for e in ESTAGIOS_WIFEED]
    PipelineEstagio.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('crm', '0014_alter_choices_wifeed'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
