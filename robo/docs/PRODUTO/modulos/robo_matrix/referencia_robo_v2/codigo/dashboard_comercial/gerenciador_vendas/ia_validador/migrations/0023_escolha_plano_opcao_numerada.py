"""Corrige aliases da escolha_plano: '1' e '2' = número da opção do menu.

Bug original: cliente respondia '2' (opção 2 = 1G Turbo, id 1648), mas o
extractor fazia substring match em '620mb' (alias do 1649) — o char '2' está
em '620mb' — e devolvia o plano errado.

Agora '1' e '2' são aliases EXATOS e ficam PRIMEIRO na lista, garantindo
match correto. Aliases textuais ficam pra cliente que digita '620', 'turbo'
etc. Menu mostrado ao cliente:

    1) Plano 620 Mega   → id 1649
    2) Plano 1G Turbo   → id 1648
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = Regra.objects.get(question_id='escolha_plano')
    except Regra.DoesNotExist:
        return

    r.extractor_config = {
        'opcoes': {
            '1649': ['1', '620',  '620mb', '620 mega'],            # opção 1 do menu = 620 Mega
            '1648': ['2', '1g',   '1giga', '1 giga', '1000', 'turbo'],   # opção 2 do menu = 1G Turbo
            # Planos extras (não aparecem no menu padrão, mas aceitos se cliente digitar)
            '1647': ['300', '300mb', '300 mega'],
            '1650': ['2g',  '2giga', '2 giga', '2000'],
        },
        'descricao_opcoes': {
            '1647': 'Plano de 300MB (R$ 79,90)',
            '1648': 'Plano de 1GB Turbo (R$ 129,90)',
            '1649': 'Plano de 620MB (R$ 99,90)',
            '1650': 'Plano de 2GB (R$ 169,90)',
        },
    }
    r.msg_erro = (
        'Não entendi 😅 Pode responder com o *número* do plano '
        '(*1* pra 620 Mega ou *2* pra 1G Turbo)?'
    )
    r.save(update_fields=['extractor_config', 'msg_erro'])
    print('  ✓ escolha_plano: aliases 1/2 numerados (corrige bug substring)')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    try:
        r = Regra.objects.get(question_id='escolha_plano')
    except Regra.DoesNotExist:
        return
    r.extractor_config = {
        'opcoes': {
            '1647': ['300', '300mb', '300 mega'],
            '1648': ['1g',  '1giga', '1 giga', '1000', 'turbo'],
            '1649': ['620', '620mb', '620 mega'],
            '1650': ['2g',  '2giga', '2 giga', '2000'],
        },
        'descricao_opcoes': {
            '1647': 'Plano de 300MB (R$ 79,90)',
            '1648': 'Plano de 1GB Turbo (R$ 129,90)',
            '1649': 'Plano de 620MB (R$ 99,90)',
            '1650': 'Plano de 2GB (R$ 169,90)',
        },
    }
    r.save(update_fields=['extractor_config'])


class Migration(migrations.Migration):
    dependencies = [('ia_validador', '0022_coleta_cep_msg_dinamica')]
    operations = [migrations.RunPython(aplicar, reverter)]
