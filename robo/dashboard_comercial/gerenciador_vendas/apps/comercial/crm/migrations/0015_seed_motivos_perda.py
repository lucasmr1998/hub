# Data migration: cria os motivos de perda padrao por tenant e converte
# o campo legado motivo_perda_categoria nas FKs motivo_perda_ref.
from django.db import migrations

# slug legado -> nome do motivo
MOTIVOS_PADRAO = [
    ('preco',               'Preço'),
    ('concorrente',         'Concorrente'),
    ('timing',              'Timing / não era o momento'),
    ('sem_orcamento',       'Sem orçamento / poder de decisão'),
    ('viabilidade_tecnica', 'Sem viabilidade técnica'),
    ('sem_resposta',        'Sumiu / sem resposta'),
    ('outro',               'Outro'),
]


def seed(apps, schema_editor):
    Tenant = apps.get_model('sistema', 'Tenant')
    MotivoPerda = apps.get_model('crm', 'MotivoPerda')
    OportunidadeVenda = apps.get_model('crm', 'OportunidadeVenda')

    for tenant in Tenant.objects.all():
        # mapa slug -> instancia, pra converter as oportunidades depois
        por_slug = {}
        for ordem, (slug, nome) in enumerate(MOTIVOS_PADRAO):
            motivo, _ = MotivoPerda.objects.get_or_create(
                tenant=tenant, nome=nome,
                defaults={'ordem': ordem, 'ativo': True},
            )
            por_slug[slug] = motivo

        # converte motivo_perda_categoria (legado) -> motivo_perda_ref
        ops = OportunidadeVenda.objects.filter(
            tenant=tenant, motivo_perda_categoria__isnull=False,
            motivo_perda_ref__isnull=True,
        )
        for op in ops:
            motivo = por_slug.get(op.motivo_perda_categoria)
            if motivo:
                op.motivo_perda_ref = motivo
                op.save(update_fields=['motivo_perda_ref'])


def reverse(apps, schema_editor):
    # Nao apaga motivos (podem ter sido editados); so limpa as FKs.
    OportunidadeVenda = apps.get_model('crm', 'OportunidadeVenda')
    OportunidadeVenda.objects.update(motivo_perda_ref=None)


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0014_alter_oportunidadevenda_motivo_perda_categoria_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
