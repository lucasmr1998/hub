"""Mensagem da coleta_cep sem em-dash e sem campos vazios.

Antes o template tinha 'Rua: {rua}  Bairro: {bairro}  Cidade: {cidade}/{estado}'
— se ViaCEP não retornava rua ou bairro, aparecia 'Rua: ' ou ainda exibia o
em-dash '—' (que o gateway WhatsApp converte pra '?').

Agora a msg é construída dinamicamente em Python via placeholders condicionais.
Como o engine usa `.format()` simples, mantemos o template enxuto: só
referenciamos os dados; o engine (engine.py:hook coleta_cep) preenche
condicionalmente.
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = Regra.objects.get(question_id='coleta_cep')
    except Regra.DoesNotExist:
        return
    # Template ENXUTO. A msg rica e dinâmica vem da confirmação
    # (confirmacao_endereco em onboarding.py:639). Evita duplicar info
    # e elimina o problema do '—' que virava '?' no WhatsApp.
    r.msg_sucesso = 'Achei seu endereço! ##1f3e0##'
    r.save(update_fields=['msg_sucesso'])
    print('  ✓ coleta_cep: msg_sucesso simplificada (confirmacao_endereco mostra detalhes)')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = Regra.objects.get(question_id='coleta_cep')
    except Regra.DoesNotExist:
        return
    r.msg_sucesso = (
        'Achei seu endereço! ##1f3e0##  '
        '*Rua:* {rua}  *Bairro:* {bairro}  *Cidade:* {cidade}/{estado}  '
        'Se algo estiver errado, me avise - senão vou prosseguir.'
    )
    r.save(update_fields=['msg_sucesso'])


class Migration(migrations.Migration):
    dependencies = [('ia_validador', '0021_menu_opcao_finalizar')]
    operations = [migrations.RunPython(aplicar, reverter)]
