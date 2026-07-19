"""Reconfigura `confirmacao_dados` pra revisão final pré-instalação.

A regra já existia (criada na seed inicial), mas estava como tipo 'opcao'.
Agora vira tipo 'confirmacao' (sim/não) mapeada pro campo dados_confirmados.

Mantém status_api_apos_sucesso='aguardando_assinatura' — quando cliente
confirma, status do lead muda automaticamente.

A mensagem é construída dinamicamente em onboarding.py interpolando todos
os campos do lead.
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    r, _ = RegraValidacao.objects.update_or_create(
        question_id='confirmacao_dados',
        defaults={
            'ordem': 145,  # entre dia_vencimento (140) e docs (170)
            'pergunta_padrao': 'Confirme seus dados, por favor.',
            'descricao': 'Revisão final de TODOS os dados coletados antes da assinatura. NÃO = transbordo.',
            'extractor_tipo': 'confirmacao',
            'extractor_config': {},
            'campo_lead_atualizar': 'dados_confirmados',
            'status_api_apos_sucesso': 'aguardando_assinatura',
            'tags_adicionar': ['Dados Confirmados'],
            'historico_status_apos_sucesso': 'dados_confirmados',
            'historico_observacoes_template': 'Cliente confirmou todos os dados — pronto pra assinatura',
            'msg_sucesso': 'Perfeito! Tudo certo com seus dados. ##263A##',
            'msg_erro': 'Pode responder *1* (Sim) se está tudo certo ou *2* (Não) se precisa corrigir?',
            'max_tentativas': 3,
            'forcar_transbordo_apos_max': True,
            'ativo': True,
        },
    )
    print('  ✓ confirmacao_dados reconfigurada (extractor=confirmacao, campo=dados_confirmados)')


def reverter(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0007_docs_msgs_e_descricoes'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
