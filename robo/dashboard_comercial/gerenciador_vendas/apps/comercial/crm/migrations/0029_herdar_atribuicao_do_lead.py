"""Preenche canal_atribuicao, fonte_atribuicao e campanha_atribuicao
em OportunidadeVenda existentes, herdando do lead correspondente
(first-touch).

Fase 2 do refactor de origem. Ver:
docs/PRODUTO/modulos/comercial/modelo_origem_lead_e_oportunidade.md

Idempotente: nao sobrescreve campos ja preenchidos.
"""
from django.db import migrations


def herdar_atribuicao(apps, schema_editor):
    Op = apps.get_model('crm', 'OportunidadeVenda')
    total = 0
    atualizados = 0
    for op in Op.objects.select_related('lead').all():
        total += 1
        if not op.lead_id:
            continue

        mudou = False
        if not op.canal_atribuicao and op.lead.canal:
            op.canal_atribuicao = op.lead.canal
            mudou = True
        if not op.fonte_atribuicao and op.lead.fonte:
            op.fonte_atribuicao = op.lead.fonte
            mudou = True
        if not op.campanha_atribuicao_id and op.lead.campanha_origem_id:
            op.campanha_atribuicao_id = op.lead.campanha_origem_id
            mudou = True

        if mudou:
            op.save(update_fields=['canal_atribuicao', 'fonte_atribuicao', 'campanha_atribuicao'])
            atualizados += 1

    print(f'  Ops total: {total} | Atualizadas: {atualizados}')


def reverter(apps, schema_editor):
    """Reverse: nao faz nada (campos novos viram null com remocao)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0028_oportunidadevenda_campanha_atribuicao_and_more'),
    ]

    operations = [
        migrations.RunPython(herdar_atribuicao, reverter),
    ]
