from django.db import migrations


ESTAGIOS_PADRAO = [
    {
        'nome': 'Novo Lead',
        'slug': 'novo',
        'ordem': 1,
        'cor_hex': '#667eea',
        'icone_fa': 'fa-user-plus',
        'tipo': 'novo',
        'is_final_ganho': False,
        'is_final_perdido': False,
        'probabilidade_padrao': 10,
        'sla_horas': 24,
        'ativo': True,
    },
    {
        'nome': 'Em Qualificação',
        'slug': 'qualificacao',
        'ordem': 2,
        'cor_hex': '#764ba2',
        'icone_fa': 'fa-search',
        'tipo': 'qualificacao',
        'is_final_ganho': False,
        'is_final_perdido': False,
        'probabilidade_padrao': 30,
        'sla_horas': 48,
        'ativo': True,
    },
    {
        'nome': 'Proposta Enviada',
        'slug': 'proposta',
        'ordem': 3,
        'cor_hex': '#f39c12',
        'icone_fa': 'fa-file-contract',
        'tipo': 'negociacao',
        'is_final_ganho': False,
        'is_final_perdido': False,
        'probabilidade_padrao': 60,
        'sla_horas': 72,
        'ativo': True,
    },
    {
        'nome': 'Aguardando Instalação',
        'slug': 'instalacao',
        'ordem': 4,
        'cor_hex': '#0ea5e9',
        'icone_fa': 'fa-tools',
        'tipo': 'fechamento',
        'is_final_ganho': False,
        'is_final_perdido': False,
        'probabilidade_padrao': 85,
        'sla_horas': 120,
        'ativo': True,
    },
    {
        'nome': 'Cliente Ativo',
        'slug': 'ativo',
        'ordem': 5,
        'cor_hex': '#059669',
        'icone_fa': 'fa-check-circle',
        'tipo': 'cliente',
        'is_final_ganho': True,
        'is_final_perdido': False,
        'probabilidade_padrao': 100,
        'sla_horas': None,
        'ativo': True,
    },
    {
        'nome': 'Perdido',
        'slug': 'perdido',
        'ordem': 6,
        'cor_hex': '#e74c3c',
        'icone_fa': 'fa-times-circle',
        'tipo': 'perdido',
        'is_final_ganho': False,
        'is_final_perdido': True,
        'probabilidade_padrao': 0,
        'sla_horas': None,
        'ativo': True,
    },
]


def seed_estagios(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    ConfiguracaoCRM = apps.get_model('crm', 'ConfiguracaoCRM')

    estagio_inicial = None
    for dados in ESTAGIOS_PADRAO:
        estagio, _ = PipelineEstagio.objects.get_or_create(
            slug=dados['slug'],
            defaults=dados,
        )
        if dados['slug'] == 'novo':
            estagio_inicial = estagio

    # Criar configuração padrão apontando para o estágio inicial
    if estagio_inicial:
        ConfiguracaoCRM.objects.get_or_create(
            pk=1,
            defaults={
                'estagio_inicial_padrao': estagio_inicial,
                'criar_oportunidade_automatico': True,
                'score_minimo_auto_criacao': 7,
                'sla_alerta_horas_padrao': 48,
            }
        )


def rollback_estagios(apps, schema_editor):
    PipelineEstagio = apps.get_model('crm', 'PipelineEstagio')
    slugs = [e['slug'] for e in ESTAGIOS_PADRAO]
    PipelineEstagio.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_estagios, rollback_estagios),
    ]
