"""
Data migration: atribui setor inicial aos dashboards ja criados em prod.

Mapeia os 14 dashboards iniciais da Nuvyon (criados pelos seeds + UI) pros 7
setores oficiais. Idempotente — so atualiza dashboards que ainda estao em
setor='outros' (default da 0002_dashboard_setor).

Mapeamento (baseado no nome):
- marketing: Leads por origem, Cobertura e viabilidade
- comercial: Funil, Motivos perda, Velocidade, Performance, Parados, Follow-up,
             Conversao por etapa, Meta diaria
- cs: Demo HubSoft, Cancelamento pre-instalacao, HubSoft Visao 360
- executivo: Executivo

Dashboards nao listados continuam em 'outros' — o user reorganiza pela UI.
"""
from django.db import migrations


def atribuir_setores(apps, schema_editor):
    Dashboard = apps.get_model('relatorios', 'Dashboard')

    # nome -> setor
    mapa = {
        '1. Leads por origem': 'marketing',
        '9. Cobertura e viabilidade': 'marketing',

        '2. Funil completo': 'comercial',
        '3. Motivos de perda': 'comercial',
        '4. Velocidade de atendimento': 'comercial',
        '5. Performance consultoras': 'comercial',
        '6. Leads parados': 'comercial',
        '7. Follow-up': 'comercial',
        '8. Conversao por etapa': 'comercial',
        '11. Meta diaria': 'comercial',

        'Demo HubSoft': 'cs',
        '10. Cancelamento pre-instalacao': 'cs',
        'HubSoft — Visao 360': 'cs',
        'HubSoft - Visao 360': 'cs',
        'HubSoft Visao 360': 'cs',

        '12. Executivo': 'executivo',
    }

    for dashboard in Dashboard.objects.filter(setor='outros'):
        novo = mapa.get(dashboard.nome)
        if novo:
            dashboard.setor = novo
            dashboard.save(update_fields=['setor', 'atualizado_em'])


def reverter(apps, schema_editor):
    # Reversao: tudo de volta pra 'outros'
    Dashboard = apps.get_model('relatorios', 'Dashboard')
    Dashboard.objects.update(setor='outros')


class Migration(migrations.Migration):
    dependencies = [
        ('relatorios', '0002_dashboard_setor'),
    ]
    operations = [
        migrations.RunPython(atribuir_setores, reverse_code=reverter),
    ]
