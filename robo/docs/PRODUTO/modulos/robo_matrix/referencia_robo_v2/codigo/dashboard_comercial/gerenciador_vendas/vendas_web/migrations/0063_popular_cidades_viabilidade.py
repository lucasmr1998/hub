from django.db import migrations

# Popula CidadeViabilidade com as cidades atendidas por regional.
# (regional, cidade, estado, cep_geral, observacao)
CIDADES = [
    ('REGIONAL - 00', 'São Luís', 'MA', '65000-000', ''),

    ('REGIONAL - 01', 'Água Branca', 'PI', '64460-000', ''),
    ('REGIONAL - 01', 'Amarante', 'PI', '64400-000', ''),
    ('REGIONAL - 01', 'Capitão de Campos', 'PI', '64270-000', ''),
    ('REGIONAL - 01', 'Demerval Lobão', 'PI', '64390-000', ''),
    ('REGIONAL - 01', 'Monsenhor Gil', 'PI', '64450-000', ''),
    ('REGIONAL - 01', 'Regeneração', 'PI', '64490-000', ''),
    ('REGIONAL - 01', 'São Pedro do Piauí', 'PI', '64430-000', ''),
    ('REGIONAL - 01', 'Teresina', 'PI', '64000-000', ''),
    ('REGIONAL - 01', 'Timon', 'MA', '65630-000', ''),

    ('REGIONAL - 02', 'Barão de Grajaú', 'MA', '65660-000', ''),
    ('REGIONAL - 02', 'Colinas', 'MA', '65690-000', ''),
    ('REGIONAL - 02', 'Floriano', 'PI', '64800-000', ''),
    ('REGIONAL - 02', 'Guadalupe', 'PI', '64840-000', ''),
    ('REGIONAL - 02', 'Jatobá', 'PI', '64275-000', ''),
    ('REGIONAL - 02', 'Matões', 'MA', '65645-000', ''),
    ('REGIONAL - 02', 'Mirador', 'MA', '65850-000', ''),
    ('REGIONAL - 02', 'Nazaré do Piauí', 'PI', '64825-000', ''),
    ('REGIONAL - 02', 'Paraibano', 'MA', '65670-000', ''),
    ('REGIONAL - 02', 'Parnarama', 'MA', '65640-000', ''),

    ('REGIONAL - 03', 'Aroazes', 'PI', '64310-000', ''),
    ('REGIONAL - 03', 'Geminiano', 'PI', '64613-000', ''),
    ('REGIONAL - 03', 'Oeiras', 'PI', '64500-000', ''),
    ('REGIONAL - 03', 'Passagem Franca', 'PI', '64395-000', ''),
    ('REGIONAL - 03', 'Picos', 'PI', '64600-000', ''),
    ('REGIONAL - 03', 'Pimenteiras', 'PI', '64320-000', ''),
    ('REGIONAL - 03', 'Valença do Piauí', 'PI', '64300-000', ''),

    ('REGIONAL - 04', 'Bom Jesus', 'PI', '64900-000', ''),
    ('REGIONAL - 04', 'Cristino Castro', 'PI', '64920-000', ''),
    ('REGIONAL - 04', 'Currais', 'PI', '64905-000', ''),
    ('REGIONAL - 04', 'Gilbués', 'PI', '64930-000', ''),
    ('REGIONAL - 04', 'Palmeira do Piauí', 'PI', '64925-000', ''),
    ('REGIONAL - 04', 'Redenção do Gurguéia', 'PI', '64915-000', ''),
    ('REGIONAL - 04', 'Santa Luz', 'PI', '64910-000', ''),
    ('REGIONAL - 04', 'São Gonçalo do Gurguéia', 'PI', '64993-000', ''),

    ('REGIONAL - 05', 'Novo Horizonte', 'PI', None, 'CEP não localizado — confirmar antes de liberar venda'),
    ('REGIONAL - 05', 'Lagoa do Sítio', 'PI', '64308-000', ''),
    ('REGIONAL - 05', 'Baixio', 'PI', None, 'CEP não localizado — confirmar antes de liberar venda'),
    ('REGIONAL - 05', 'Conceição do Canindé', 'PI', '64740-000', ''),
    ('REGIONAL - 05', 'Inhuma', 'PI', '64535-000', ''),
    ('REGIONAL - 05', 'Baixas', 'PI', None, 'CEP não localizado — confirmar antes de liberar venda'),
    ('REGIONAL - 05', 'Ipiranga', 'PI', '64540-000', ''),
    ('REGIONAL - 05', 'São José', 'PI', '64625-000', 'Nome genérico — confirmar município exato (possível duplicidade)'),
    ('REGIONAL - 05', 'Dom Expedito', 'PI', '64620-000', ''),
]


def popular_cidades(apps, schema_editor):
    CidadeViabilidade = apps.get_model('vendas_web', 'CidadeViabilidade')
    for regional, cidade, estado, cep, observacao in CIDADES:
        CidadeViabilidade.objects.get_or_create(
            cidade=cidade,
            estado=estado,
            cep=cep,
            defaults={
                'regional': regional,
                'observacao': observacao or None,
                'ativo': True,
            },
        )


def remover_cidades(apps, schema_editor):
    CidadeViabilidade = apps.get_model('vendas_web', 'CidadeViabilidade')
    for regional, cidade, estado, cep, _observacao in CIDADES:
        CidadeViabilidade.objects.filter(
            cidade=cidade, estado=estado, cep=cep, regional=regional,
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('vendas_web', '0062_cidadeviabilidade_regional'),
    ]

    operations = [
        migrations.RunPython(popular_cidades, remover_cidades),
    ]
