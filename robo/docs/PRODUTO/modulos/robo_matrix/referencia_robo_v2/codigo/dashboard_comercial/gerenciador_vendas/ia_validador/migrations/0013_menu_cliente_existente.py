"""Adiciona regra de validação pro menu de cliente existente.

Quando o CPF informado já é cliente Hubsoft, o bot apresenta o menu:
  1) Contratar um novo serviço      → transbordo
  2) Fazer upgrade de plano         → transbordo
  3) Acompanhar status instalação   → engine busca OS no Hubsoft e mostra
  4) Falar com Atendimento          → transbordo

A regra é só de validação da opção (1-4). A lógica de "o que fazer"
fica no engine.py via hook especial.
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')

    Regra.objects.update_or_create(
        question_id='menu_cliente_existente',
        defaults={
            'ordem': 5,   # bem no início (após coleta_cpf)
            'descricao': 'Menu pra clientes Hubsoft existentes',
            'pergunta_padrao': (
                'Como posso te ajudar hoje?\n\n'
                '1) Contratar um novo serviço\n'
                '2) Fazer upgrade de plano\n'
                '3) Acompanhar status da instalação\n'
                '4) Falar com Atendimento'
            ),
            'extractor_tipo': 'opcao',
            'extractor_config': {
                'opcoes': {
                    'novo_servico':   ['1', 'novo', 'contratar', 'novo serviço'],
                    'upgrade_plano':  ['2', 'upgrade', 'mudar plano'],
                    'acompanhar_os':  ['3', 'acompanhar', 'instalação', 'instalacao', 'status'],
                    'atendimento':    ['4', 'atendimento', 'falar', 'atendente'],
                }
            },
            'campo_lead_atualizar': '',  # não persiste no lead — só rotear
            'msg_sucesso': '',           # engine substitui dinamicamente
            'msg_erro': 'Por favor escolha 1, 2, 3 ou 4.',
            'max_tentativas': 3,
            'permite_pular': False,
        }
    )
    print('  ✓ menu_cliente_existente: regra criada')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    Regra.objects.filter(question_id='menu_cliente_existente').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0012_fluxo_agendamento_instalacao'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
