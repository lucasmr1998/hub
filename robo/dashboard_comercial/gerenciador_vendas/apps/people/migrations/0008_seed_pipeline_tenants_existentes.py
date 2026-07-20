"""
Back-fill do pipeline de recrutamento.

O signal de provisionamento (apps/people/signals.py) so dispara quando o modulo
People PASSA A SER ativado. Quem ja estava com ele ligado antes deste commit
nunca passa por essa transicao, e ficaria com o board de recrutamento sem coluna
nenhuma.

Data migration e nao comando manual de proposito: o rebuild de producao aplica
migration sozinho, entao ninguem precisa lembrar de rodar nada. Um comando a ser
executado a mao e exatamente o passo que se esquece.

Idempotente: `semear_padrao` nao faz nada se o escopo ja tiver etapa.
"""
from django.db import migrations


ETAPAS_PADRAO = [
    ('Triagem', 1, 3),
    ('Histórico', 2, 3),
    ('Teste Comportamental', 3, 5),
    ('Seleção', 4, 5),
    ('Teste prático', 5, 5),
    ('Avaliação Gestor', 6, 3),
    ('Admissão', 7, 5),
]


def semear(apps, schema_editor):
    """
    Semeia as etapas nos tenants que ja tem People ativo.

    As etapas estao repetidas aqui, e nao importadas de estados_recrutamento, de
    proposito: data migration precisa continuar rodando igual daqui a um ano,
    mesmo que a lista do codigo mude. Importar faria esta migration reescrever o
    passado conforme o presente.
    """
    Tenant = apps.get_model('sistema', 'Tenant')
    EtapaPipeline = apps.get_model('people', 'EtapaPipeline')

    for tenant in Tenant.objects.filter(modulo_people=True):
        ja_tem = EtapaPipeline.objects.filter(tenant=tenant,
                                              unidade__isnull=True).exists()
        if ja_tem:
            continue

        EtapaPipeline.objects.bulk_create([
            EtapaPipeline(tenant=tenant, unidade=None, nome=nome,
                          ordem=ordem, sla_dias=sla, ativa=True)
            for nome, ordem, sla in ETAPAS_PADRAO
        ])


def desfazer(apps, schema_editor):
    """
    Nao remove nada.

    Etapa pode ter candidato apontando pra ela. Apagar no reverse deixaria
    orfao, e reverter uma migration nao deveria destruir dado de cliente.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0007_linkcandidatura'),
        ('sistema', '0017_tenant_modulo_people_tenant_plano_people_and_more'),
    ]

    operations = [
        migrations.RunPython(semear, desfazer),
    ]
