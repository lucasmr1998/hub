"""Adiciona opção 5 'Finalizar atendimento' no menu_cliente_existente."""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = Regra.objects.get(question_id='menu_cliente_existente')
    except Regra.DoesNotExist:
        return

    r.pergunta_padrao = (
        'Como posso te ajudar hoje?\n\n'
        '1) Contratar um novo serviço\n'
        '2) Fazer upgrade de plano\n'
        '3) Acompanhar status da instalação\n'
        '4) Falar com Atendimento\n'
        '5) Finalizar atendimento'
    )
    r.extractor_config = {
        'opcoes': {
            'novo_servico':   ['1', 'novo', 'contratar', 'novo serviço'],
            'upgrade_plano':  ['2', 'upgrade', 'mudar plano'],
            'acompanhar_os':  ['3', 'acompanhar', 'instalação', 'instalacao', 'status'],
            'atendimento':    ['4', 'atendimento', 'falar', 'atendente'],
            'finalizar':      ['5', 'finalizar', 'encerrar', 'sair', 'tchau', 'obrigado', 'obrigada'],
        }
    }
    r.msg_erro = (
        'Não entendi 😅 Pode responder com o número da opção '
        '(*1*, *2*, *3*, *4* ou *5*)?'
    )
    r.save(update_fields=['pergunta_padrao', 'extractor_config', 'msg_erro'])
    print('  ✓ menu_cliente_existente: opção 5 (finalizar) adicionada')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = Regra.objects.get(question_id='menu_cliente_existente')
    except Regra.DoesNotExist:
        return
    r.pergunta_padrao = (
        'Como posso te ajudar hoje?\n\n'
        '1) Contratar um novo serviço\n'
        '2) Fazer upgrade de plano\n'
        '3) Acompanhar status da instalação\n'
        '4) Falar com Atendimento'
    )
    r.extractor_config = {
        'opcoes': {
            'novo_servico':   ['1', 'novo', 'contratar', 'novo serviço'],
            'upgrade_plano':  ['2', 'upgrade', 'mudar plano'],
            'acompanhar_os':  ['3', 'acompanhar', 'instalação', 'instalacao', 'status'],
            'atendimento':    ['4', 'atendimento', 'falar', 'atendente'],
        }
    }
    r.msg_erro = 'Por favor escolha 1, 2, 3 ou 4.'
    r.save(update_fields=['pergunta_padrao', 'extractor_config', 'msg_erro'])


class Migration(migrations.Migration):
    dependencies = [('ia_validador', '0020_dia_vencimento_aliases')]
    operations = [migrations.RunPython(aplicar, reverter)]
