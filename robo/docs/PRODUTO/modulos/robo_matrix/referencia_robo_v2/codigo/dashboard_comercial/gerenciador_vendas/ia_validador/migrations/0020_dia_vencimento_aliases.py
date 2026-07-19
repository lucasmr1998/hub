"""Aliases da regra dia_vencimento: aceita 1/2/3/4 (numero da opcao),
1/5/15/20 (dia real) e 'Dia X' (texto)."""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = Regra.objects.get(question_id='dia_vencimento')
    except Regra.DoesNotExist:
        return

    # Mapeia opção numerada (1-4) + dia real + texto "Dia X" → id RP correto.
    # Ordem dos aliases: número da opção PRIMEIRO (1-4 do menu) — se cliente
    # escrever "2", interpreta como "Dia 5" (opção 2) e não como dia 2.
    r.extractor_config = {
        'opcoes': {
            '28': ['1',  'dia 1',  'um',     'primeiro'],          # opção 1 = Dia 1
            '9':  ['2',  '5',  'dia 5',  'cinco'],                 # opção 2 = Dia 5
            '5':  ['3',  '15', 'dia 15', 'quinze'],                # opção 3 = Dia 15
            '6':  ['4',  '20', 'dia 20', 'vinte'],                 # opção 4 = Dia 20
        }
    }
    r.msg_erro = (
        'Não entendi 😅 Pode responder com o número da opção '
        '(*1*, *2*, *3* ou *4*) ou o dia (*1*, *5*, *15* ou *20*)?'
    )
    r.save(update_fields=['extractor_config', 'msg_erro'])
    print('  ✓ dia_vencimento: aliases atualizados (1-4 opção + dias + texto)')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = Regra.objects.get(question_id='dia_vencimento')
    except Regra.DoesNotExist:
        return
    r.extractor_config = {
        'opcoes': {
            '5':  ['10', '15'],
            '6':  ['20', '25'],
            '9':  ['5'],
            '28': ['1'],
        }
    }
    r.msg_erro = 'Pode escolher uma das datas: 1, 5, 15 ou 20?'
    r.save(update_fields=['extractor_config', 'msg_erro'])


class Migration(migrations.Migration):
    dependencies = [('ia_validador', '0019_log_endpoint_new_service')]
    operations = [migrations.RunPython(aplicar, reverter)]
