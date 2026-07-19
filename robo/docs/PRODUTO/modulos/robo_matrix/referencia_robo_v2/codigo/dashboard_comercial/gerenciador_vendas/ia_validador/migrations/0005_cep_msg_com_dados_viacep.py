"""Atualiza msg_sucesso da regra coleta_cep para mostrar os dados do ViaCEP.

Após validar com sucesso, em vez de "Endereço encontrado!" genérico, mostra
exatamente o que o ViaCEP retornou para o cliente confirmar visualmente.

Como a sequência foi reordenada (cep ANTES de rua/bairro/cidade), o ViaCEP
preenche esses campos automaticamente — a próxima pergunta vira "número da
residência". O cliente vê os dados do CEP e, se quiser corrigir, pode falar
com atendente (transbordo).

Placeholders disponíveis no template (engine usa `.format()`):
- {cep}, {rua}, {bairro}, {cidade}, {estado}
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = RegraValidacao.objects.get(question_id='coleta_cep')
        r.msg_sucesso = (
            'Achei seu endereço! ##1f3e0##  '
            '*Rua:* {rua}  *Bairro:* {bairro}  *Cidade:* {cidade}/{estado}  '
            'Se algo estiver errado, me avise — senão vou prosseguir.'
        )
        r.msg_erro = (
            'Esse CEP não foi localizado. Pode conferir? '
            'Formato esperado: 64000-000 (8 dígitos).'
        )
        r.save(update_fields=['msg_sucesso', 'msg_erro'])
        print(f'  ✓ coleta_cep atualizada')
    except RegraValidacao.DoesNotExist:
        print(f'  ⚠ coleta_cep não existe — pulando')


def reverter(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = RegraValidacao.objects.get(question_id='coleta_cep')
        r.msg_sucesso = 'Endereço encontrado! ##263A##'
        r.msg_erro = 'Esse CEP parece incorreto. Pode conferir? São 8 dígitos (Ex: 64000-000).'
        r.save(update_fields=['msg_sucesso', 'msg_erro'])
    except RegraValidacao.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0004_acoes_e_mensagens'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
