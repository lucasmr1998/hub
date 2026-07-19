"""Reconfigura a regra `confirmacao_endereco` para confirmar dados do ViaCEP.

Antes era tipo 'opcao' (URA antiga ura_7). Agora vira 'confirmacao' (sim/não)
mapeada pro campo LeadProspecto.endereco_confirmado.

A pergunta padrão é dinamica: mostra rua/bairro/cidade do lead pra cliente
revisar. O texto exibido vem do onboarding.py via mensagem_inicial.
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    r, _ = RegraValidacao.objects.update_or_create(
        question_id='confirmacao_endereco',
        defaults={
            'ordem': 65,  # logo após coleta_cep (60) e antes de coleta_rua (70)
            'pergunta_padrao': 'Está tudo certo com esse endereço?',
            'descricao': 'Confirma dados retornados pelo ViaCEP. Se NÃO, limpa cidade/bairro/rua.',
            'extractor_tipo': 'confirmacao',
            'extractor_config': {},
            'campo_lead_atualizar': 'endereco_confirmado',
            'msg_sucesso': '',  # próxima pergunta já fala
            'msg_erro': 'Pode responder *Sim* se está correto, ou *Não* se precisa corrigir?',
            'max_tentativas': 3,
            'permite_pular': False,
            'forcar_transbordo_apos_max': False,
            'ativo': True,
        },
    )
    print(f'  ✓ confirmacao_endereco reconfigurada como tipo confirmacao')


def reverter(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    RegraValidacao.objects.filter(question_id='confirmacao_endereco').update(
        extractor_tipo='opcao',
        campo_lead_atualizar='',
        extractor_config={'opcoes': {
            'corretos': ['1', 'sim', 'corretos', 'certo', 'pode'],
            'corrigir': ['2', 'não', 'nao', 'corrigir', 'errado'],
        }},
    )


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0005_cep_msg_com_dados_viacep'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
