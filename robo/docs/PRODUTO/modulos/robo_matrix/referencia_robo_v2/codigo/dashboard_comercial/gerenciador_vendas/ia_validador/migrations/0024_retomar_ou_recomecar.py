"""Regra `retomar_ou_recomecar`.

Quando o cliente volta (nova sessão) e já tinha progresso de um
atendimento anterior, o bot mostra o que já foi coletado e pergunta:
  1) Continuar de onde parei
  2) Começar de novo

O texto da pergunta (com o resumo dos dados) é montado dinamicamente
pelo onboarding; aqui só registramos a regra de validação da opção.
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    Regra.objects.update_or_create(
        question_id='retomar_ou_recomecar',
        defaults={
            'ordem': 2,  # bem no começo (logo após identificação)
            'descricao': 'Cliente voltou com progresso: continuar ou recomeçar',
            'pergunta_padrao': (
                'Vi que você já tinha um cadastro em andamento. '
                'Quer continuar de onde parou ou começar de novo? '
                '1=Continuar / 2=Começar de novo.'
            ),
            'extractor_tipo': 'opcao',
            'extractor_config': {
                'opcoes': {
                    'continuar': ['1', 'continuar', 'continua', 'seguir', 'de onde parei'],
                    'recomecar': ['2', 'começar', 'comecar', 'recomeçar', 'recomecar',
                                  'de novo', 'do zero', 'novo'],
                }
            },
            'campo_lead_atualizar': '',   # engine trata no hook
            'msg_sucesso': '',
            'msg_erro': 'Por favor responda *1* (continuar) ou *2* (começar de novo).',
            'max_tentativas': 3,
            'permite_pular': False,
            'ativo': True,
        }
    )
    print('  ✓ retomar_ou_recomecar: regra criada')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    Regra.objects.filter(question_id='retomar_ou_recomecar').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0023_escolha_plano_opcao_numerada'),
    ]
    operations = [migrations.RunPython(aplicar, reverter)]
