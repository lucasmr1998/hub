"""
Contagem de visitantes por link, pra tela poder mostrar taxa de conversao.

O back-fill marca `medindo_visitas_desde` = agora nos links que JA EXISTEM. Eles
tem candidatura sem visita correspondente, entao a divisao daria numero acima de
100%. Com a data gravada, a tela diz "medindo visitas desde <data>" ate a
contagem alcancar, em vez de exibir uma taxa quebrada no primeiro dia.

Nao ha back-fill de `visitas`: nao ha de onde tirar. Visita passada nao foi
registrada em lugar nenhum, e inventar numero seria pior que admitir a lacuna.
"""
from django.db import migrations, models
from django.utils import timezone


def marcar_inicio_da_medicao(apps, schema_editor):
    Link = apps.get_model('people', 'LinkCandidatura')
    Link.objects.filter(medindo_visitas_desde__isnull=True).update(
        medindo_visitas_desde=timezone.now())


def desfazer(apps, schema_editor):
    """Nada a desfazer: as colunas saem no reverse dos AddField."""


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0017_candidato_etapa_desde'),
    ]

    operations = [
        migrations.AddField(
            model_name='linkcandidatura',
            name='medindo_visitas_desde',
            field=models.DateTimeField(blank=True, help_text='Link criado antes da medicao tem candidatura sem visita correspondente, e a taxa mentiria. Guardar a data permite dizer isso em vez de exibir um numero quebrado.', null=True, verbose_name='Medindo visitas desde'),
        ),
        migrations.AddField(
            model_name='linkcandidatura',
            name='visitas',
            field=models.PositiveIntegerField(default=0, help_text='Visitantes unicos que ABRIRAM a pagina. Nao e clique: quem clica e desiste antes de carregar nao conta.', verbose_name='Visitas'),
        ),
        migrations.RunPython(marcar_inicio_da_medicao, desfazer),
    ]
