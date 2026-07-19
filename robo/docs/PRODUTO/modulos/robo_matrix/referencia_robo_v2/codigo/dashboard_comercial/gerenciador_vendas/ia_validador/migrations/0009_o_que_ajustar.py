"""Cria regra `o_que_ajustar` — dispara quando cliente nega dados_confirmados.

Após receber a opção (1=endereço, 2=dados pessoais, 3=plano), a API limpa
os campos correspondentes do lead e re-pergunta tudo até voltar pra
confirmacao_dados.
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    RegraValidacao.objects.update_or_create(
        question_id='o_que_ajustar',
        defaults={
            'ordem': 146,  # logo depois de confirmacao_dados (145)
            'pergunta_padrao': 'O que você quer ajustar?',
            'descricao': 'Cliente negou os dados finais — escolhe categoria pra corrigir.',
            'extractor_tipo': 'opcao',
            'extractor_config': {
                'opcoes': {
                    'endereco':       ['1', 'endereço', 'endereco', 'address'],
                    'dados_pessoais': ['2', 'dados pessoais', 'pessoais', 'dados'],
                    'plano':          ['3', 'plano', 'plano selecionado'],
                },
            },
            'campo_lead_atualizar': 'tipo_ajuste',
            'status_api_apos_sucesso': '',
            'tags_adicionar': [],
            'historico_status_apos_sucesso': 'ajuste_solicitado',
            'historico_observacoes_template': 'Cliente quer ajustar: {answer}',
            'msg_sucesso': 'Beleza, vamos corrigir!',
            'msg_erro': 'Por favor responda *1* (Endereço), *2* (Dados pessoais) ou *3* (Plano).',
            'max_tentativas': 3,
            'forcar_transbordo_apos_max': True,
            'ativo': True,
        },
    )
    print('  ✓ o_que_ajustar criada (extractor=opcao, campo=tipo_ajuste)')


def reverter(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0008_confirmacao_dados_final'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
