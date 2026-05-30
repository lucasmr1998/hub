"""Seed do motivo de sistema 'Encerramento automatico' (codigo=auto_inatividade)
em todos os tenants existentes. Idempotente. Usado pelo command encerrar_inativos
e tambem disponivel pra agentes selecionarem no encerramento manual.
"""
from django.db import migrations


def seed_motivo_auto(apps, schema_editor):
    Tenant = apps.get_model('sistema', 'Tenant')
    Motivo = apps.get_model('inbox', 'MotivoEncerramento')
    for t in Tenant.objects.all():
        if not Motivo.objects.filter(tenant_id=t.id, codigo='auto_inatividade').exists():
            Motivo.objects.create(
                tenant_id=t.id,
                codigo='auto_inatividade',
                nome='Encerramento automático',
                sistema=True,
                cor_hex='#94a3b8',
                ativo=True,
                ordem=999,
            )


def reverse(apps, schema_editor):
    Motivo = apps.get_model('inbox', 'MotivoEncerramento')
    Motivo.objects.filter(codigo='auto_inatividade', sistema=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('inbox', '0011_configuracaoinbox_encerramento_auto_ativo_and_more'),
        ('sistema', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed_motivo_auto, reverse),
    ]
