"""Adiciona regras `confirmacao_plano` e `pergunta_finalizar`.

- confirmacao_plano: depois de cliente escolher plano, mostra descrição
  rica + pede SIM/NÃO. Se NÃO, engine limpa id_plano_rp e volta a perguntar.
- pergunta_finalizar: usada após cliente ver OS (menu opção 3) OU após
  agendar instalação. 1=voltar ao menu / 2=encerrar atendimento.

Também desativa `coleta_rg` (RG não é mais coletado — vem pelas fotos).
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')

    # Desativa coleta_rg (mantém registro pra auditoria, mas inativo)
    rg = Regra.objects.filter(question_id='coleta_rg').first()
    if rg:
        rg.ativo = False
        rg.save()
        print('  ✓ coleta_rg desativada')

    # ── confirmacao_plano ──────────────────────────────────────────
    Regra.objects.update_or_create(
        question_id='confirmacao_plano',
        defaults={
            'ordem': 165,   # entre escolha_plano (160) e dia_vencimento (170)
            'descricao': 'Confirma o plano escolhido após ver descrição rica',
            'pergunta_padrao': (
                'Confirma a contratação do plano selecionado? '
                '1=Sim / 2=Não, quero ver outro.'
            ),
            'extractor_tipo': 'confirmacao',
            'extractor_config': {},
            'campo_lead_atualizar': 'plano_confirmado',
            'msg_sucesso': 'Plano confirmado! ##2705##',
            'msg_erro': 'Pode responder: *1* pra confirmar ou *2* pra trocar o plano.',
            'max_tentativas': 3,
            'permite_pular': False,
            'ativo': True,
        }
    )
    print('  ✓ confirmacao_plano: regra criada')

    # ── pergunta_finalizar ─────────────────────────────────────────
    Regra.objects.update_or_create(
        question_id='pergunta_finalizar',
        defaults={
            'ordem': 999,   # bem no final
            'descricao': 'Pergunta se cliente quer continuar (menu) ou encerrar',
            'pergunta_padrao': (
                'Posso te ajudar com mais alguma coisa? '
                '1=Voltar ao menu / 2=Não, obrigado!'
            ),
            'extractor_tipo': 'opcao',
            'extractor_config': {
                'opcoes': {
                    'voltar_menu': ['1', 'sim', 'voltar', 'menu'],
                    'encerrar':    ['2', 'não', 'nao', 'obrigado', 'obg'],
                }
            },
            'campo_lead_atualizar': '',  # engine seta status_api conforme escolha
            'msg_sucesso': '',
            'msg_erro': 'Por favor responda *1* (voltar ao menu) ou *2* (encerrar).',
            'max_tentativas': 3,
            'permite_pular': False,
            'ativo': True,
        }
    )
    print('  ✓ pergunta_finalizar: regra criada')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    Regra.objects.filter(question_id__in=[
        'confirmacao_plano', 'pergunta_finalizar'
    ]).delete()
    rg = Regra.objects.filter(question_id='coleta_rg').first()
    if rg:
        rg.ativo = True
        rg.save()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0015_confirmacao_dados_status_pendente'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
