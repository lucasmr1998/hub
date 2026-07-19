"""Mensagem inicial de WhatsApp padrão do pipeline Wifeed (editável na tela de admin)."""
from django.db import migrations

DEFAULTS = {
    'wifeed': 'Olá {primeiro_nome}! 😊 Aqui é da *Megalink Internet*. Vi seu cadastro no '
              'nosso WiFi e posso te apresentar nossos planos de internet. Podemos falar?',
}


def aplicar(apps, schema_editor):
    M = apps.get_model('crm', 'MensagemPipeline')
    for tipo, msg in DEFAULTS.items():
        M.objects.get_or_create(pipeline_tipo=tipo, defaults={'mensagem': msg, 'ativo': True})


def reverter(apps, schema_editor):
    M = apps.get_model('crm', 'MensagemPipeline')
    M.objects.filter(pipeline_tipo__in=list(DEFAULTS)).delete()


class Migration(migrations.Migration):
    dependencies = [('crm', '0015_seed_estagios_wifeed')]
    operations = [migrations.RunPython(aplicar, reverter)]
