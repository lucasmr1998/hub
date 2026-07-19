"""Após cliente confirmar os dados pessoais+endereço+plano, marca o lead
como 'pendente' pra que o serviço de sincronização Hubsoft cadastre o
prospecto corretamente.

Antes: a regra confirmacao_dados só setava o flag dados_confirmados=True,
sem mudar o status_api. O serviço de sync só processa leads com
status_api='pendente'.

Agora: confirmacao_dados (SIM) → status_api='pendente' + tag 'Dados
Confirmados'. Daí o sincronizador encontra e tenta cadastrar.
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')

    r = Regra.objects.filter(question_id='confirmacao_dados').first()
    if not r:
        print('  ! confirmacao_dados não encontrada — pulando')
        return

    r.status_api_apos_sucesso = 'pendente'
    tags = list(r.tags_adicionar or [])
    if 'Dados Confirmados' not in tags:
        tags.append('Dados Confirmados')
    r.tags_adicionar = tags
    r.historico_status_apos_sucesso = 'dados_confirmados'
    r.historico_observacoes_template = (
        'Cliente confirmou os dados — pronto pra sincronização Hubsoft'
    )
    r.msg_sucesso = (
        'Perfeito! Tudo certo com seus dados. ##263A##\n\n'
        'Agora preciso só de algumas fotos pra finalizar.'
    )
    r.save()
    print('  ✓ confirmacao_dados: status_api=pendente + tag Dados Confirmados')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    r = Regra.objects.filter(question_id='confirmacao_dados').first()
    if r:
        r.status_api_apos_sucesso = ''
        tags = [t for t in (r.tags_adicionar or []) if t != 'Dados Confirmados']
        r.tags_adicionar = tags
        r.save()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0014_fluxo_pos_docs_direto'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
