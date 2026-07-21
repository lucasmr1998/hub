"""
Campo `etapa_desde`, que faz o `sla_dias` deixar de ser campo morto.

O back-fill importa: sem ele todo candidato que ja esta no pipeline ficaria com
`etapa_desde` nulo, o board nao mostraria atraso pra ninguem, e o recurso
nasceria parecendo quebrado justamente pra quem ja usa.

A fonte do back-fill e o `HistoricoCandidato`, que registra cada movimento com
data. Candidato sem historico da etapa atual (entrou pela candidatura publica e
nunca foi movido) cai pro `criado_em`, que e quando ele de fato chegou.
"""
from django.db import migrations, models


def preencher_etapa_desde(apps, schema_editor):
    Candidato = apps.get_model('people', 'Candidato')
    Historico = apps.get_model('people', 'HistoricoCandidato')

    # all_tenants nao existe no model historico da migration; aqui o manager
    # padrao ja e o cru, sem filtro de tenant, que e o que se quer num back-fill.
    ultimo_por_candidato = {}
    for registro in Historico.objects.order_by('criado_em').values(
            'candidato_id', 'para_etapa', 'criado_em'):
        ultimo_por_candidato[(registro['candidato_id'],
                              registro['para_etapa'])] = registro['criado_em']

    atualizados = []
    for candidato in Candidato.objects.select_related('etapa').exclude(
            etapa__isnull=True).only('id', 'criado_em', 'etapa'):
        chave = (candidato.id, candidato.etapa.nome)
        candidato.etapa_desde = ultimo_por_candidato.get(chave,
                                                         candidato.criado_em)
        atualizados.append(candidato)

    if atualizados:
        Candidato.objects.bulk_update(atualizados, ['etapa_desde'],
                                      batch_size=500)


def desfazer(apps, schema_editor):
    """Nada a desfazer: a coluna inteira sai no reverse do AddField."""


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0016_candidato_dados_custom_campocandidatura'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidato',
            name='etapa_desde',
            field=models.DateTimeField(blank=True, help_text='Quando entrou na etapa atual. Base do indicador de atraso.', null=True, verbose_name='Nesta etapa desde'),
        ),
        migrations.RunPython(preencher_etapa_desde, desfazer),
    ]
