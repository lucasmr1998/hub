"""Semeia os estágios dos pipelines PÓS-VENDA (cliente existente):
novo serviço, upgrade de plano e atendimento — alinhados ao fluxo real
(conversa → coleta → webdriver HubSoft → sync Matrix).

Os 6 estágios já existentes ficam no pipeline 'aquisicao' (default da AddField).
"""
from django.db import migrations


ESTAGIOS_POSVENDA = [
    # (slug, nome, pipeline_tipo, ordem, cor, icone, prob, ganho, perdido)
    # ── NOVO SERVIÇO ────────────────────────────────────────────────
    ('ns_coletando',     'Coletando Dados',        'novo_servico', 1, '#6c757d', 'fa-clipboard-list', 20, False, False),
    ('ns_proc_hubsoft',  'Processando no HubSoft', 'novo_servico', 2, '#0d6efd', 'fa-robot',          60, False, False),
    ('ns_sync_matrix',   'Abrindo OS (Matrix)',    'novo_servico', 3, '#6610f2', 'fa-sync',           80, False, False),
    ('ns_concluido',     'Serviço Criado',         'novo_servico', 4, '#198754', 'fa-check-circle',  100, True,  False),
    ('ns_falha',         'Falha',                  'novo_servico', 5, '#dc3545', 'fa-times-circle',    0, False, True),
    # ── UPGRADE DE PLANO ────────────────────────────────────────────
    ('up_andamento',     'Em Andamento',           'upgrade', 1, '#fd7e14', 'fa-comments',     30, False, False),
    ('up_proc_hubsoft',  'Migrando no HubSoft',    'upgrade', 2, '#0d6efd', 'fa-robot',        70, False, False),
    ('up_concluido',     'Upgrade Aplicado',       'upgrade', 3, '#198754', 'fa-check-circle', 100, True,  False),
    ('up_falha',         'Falha',                  'upgrade', 4, '#dc3545', 'fa-times-circle',   0, False, True),
    # ── ATENDIMENTO / SUPORTE ───────────────────────────────────────
    ('at_andamento',     'Em Atendimento',         'atendimento', 1, '#20c997', 'fa-headset',      40, False, False),
    ('at_concluido',     'Concluído',              'atendimento', 2, '#198754', 'fa-check-circle', 100, True,  False),
]


def aplicar(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    for (slug, nome, ptipo, ordem, cor, icone, prob, ganho, perdido) in ESTAGIOS_POSVENDA:
        PipelineEstagio.objects.update_or_create(
            slug=slug,
            defaults={
                'nome': nome,
                'pipeline_tipo': ptipo,
                'ordem': ordem,
                'cor_hex': cor,
                'icone_fa': icone,
                'tipo': 'cliente',
                'probabilidade_padrao': prob,
                'is_final_ganho': ganho,
                'is_final_perdido': perdido,
                'ativo': True,
            },
        )


def reverter(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    slugs = [e[0] for e in ESTAGIOS_POSVENDA]
    PipelineEstagio.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('crm', '0005_oportunidadevenda_new_service_oportunidadevenda_tipo_and_more'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
