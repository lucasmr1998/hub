"""Mensagens iniciais de WhatsApp padrão por pipeline (editáveis na tela de admin)."""
from django.db import migrations

DEFAULTS = {
    'aquisicao':    'Olá {primeiro_nome}! 😊 Aqui é da *Megalink Internet*. Vi seu interesse '
                    'em nossos planos e posso te ajudar a finalizar sua contratação. Podemos falar?',
    'novo_servico': 'Olá {primeiro_nome}! Aqui é da *Megalink Internet*. Vi que você tem '
                    'interesse em contratar um novo serviço. Posso te ajudar? 🙂',
    'upgrade':      'Olá {primeiro_nome}! 🚀 Aqui é da *Megalink Internet*. Que tal turbinar '
                    'seu plano? Posso te apresentar as opções de upgrade disponíveis.',
    'atendimento':  'Olá {primeiro_nome}! Aqui é da *Megalink Internet*, sobre o seu '
                    'atendimento. Como posso te ajudar hoje?',
    'indicacao':    'Olá {primeiro_nome}! 😊 Você foi indicado(a) para a *Megalink Internet*. '
                    'Posso te apresentar nossos planos de internet?',
}


def aplicar(apps, schema_editor):
    M = apps.get_model('crm', 'MensagemPipeline')
    for tipo, msg in DEFAULTS.items():
        M.objects.get_or_create(pipeline_tipo=tipo, defaults={'mensagem': msg, 'ativo': True})


def reverter(apps, schema_editor):
    M = apps.get_model('crm', 'MensagemPipeline')
    M.objects.filter(pipeline_tipo__in=list(DEFAULTS)).delete()


class Migration(migrations.Migration):
    dependencies = [('crm', '0009_mensagempipeline')]
    operations = [migrations.RunPython(aplicar, reverter)]
