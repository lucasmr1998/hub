"""Adiciona regra `coleta_tipo_residencia` (1=casa térrea / 2=apto / 3=cond).

Vem ANTES de coleta_ponto_referencia na sequência. Define qual mensagem
de complemento o bot vai exibir (casa térrea só pede ref externa; apto e
condomínio pedem detalhes específicos).
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')

    Regra.objects.update_or_create(
        question_id='coleta_tipo_residencia',
        defaults={
            'ordem': 85,   # entre coleta_numero (70) e coleta_ponto_referencia (80)
            'descricao': 'Tipo de residência (casa térrea / apto / condomínio)',
            'pergunta_padrao': (
                'Que tipo de imóvel você reside?\n'
                '1=Casa térrea / 2=Apartamento / 3=Condomínio fechado.'
            ),
            'extractor_tipo': 'opcao',
            'extractor_config': {
                'opcoes': {
                    'casa_terrea': ['1', 'casa', 'térrea', 'terrea', 'sobrado'],
                    'apartamento': ['2', 'apto', 'apartamento', 'apartmento'],
                    'condominio':  ['3', 'condomínio', 'condominio', 'cond'],
                }
            },
            'campo_lead_atualizar': 'tipo_residencia',
            'msg_sucesso': 'Anotado! ##263A##',
            'msg_erro': 'Por favor responda *1* (Casa), *2* (Apartamento) ou *3* (Condomínio).',
            'max_tentativas': 3,
            'permite_pular': False,
            'ativo': True,
        }
    )
    print('  ✓ coleta_tipo_residencia: regra criada')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    Regra.objects.filter(question_id='coleta_tipo_residencia').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0016_confirmacao_plano_e_finalizar'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
