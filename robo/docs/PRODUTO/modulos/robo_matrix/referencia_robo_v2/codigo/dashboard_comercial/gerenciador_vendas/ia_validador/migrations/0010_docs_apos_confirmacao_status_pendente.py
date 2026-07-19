"""Reorganiza o flow final: docs APÓS confirmação e status=pendente no último doc.

Mudanças nas regras:

- `confirmacao_dados`: deixa de mudar status_api. Agora apenas marca o flag
  `dados_confirmados=True` e segue pros docs. Tag 'Dados Confirmados' continua.
- `documentacao_verso_doc`: passa a setar status_api='pendente' e adicionar
  tag 'Cadastro Concluído'. É o último passo automatizado — depois disso o
  status=pendente faz o STATUS_ROTAS rotear pra atendente (em_processamento)
  fechar contrato + agendar instalação manualmente.
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')

    confirmacao = RegraValidacao.objects.filter(question_id='confirmacao_dados').first()
    if confirmacao:
        confirmacao.status_api_apos_sucesso = ''
        confirmacao.msg_sucesso = 'Perfeito! Tudo certo com seus dados. ##263A## Agora preciso só de algumas fotos pra finalizar.'
        confirmacao.save()
        print('  ✓ confirmacao_dados: status_api zerado (agora só marca o flag)')

    verso = RegraValidacao.objects.filter(question_id='documentacao_verso_doc').first()
    if verso:
        verso.status_api_apos_sucesso = 'pendente'
        tags = list(verso.tags_adicionar or [])
        if 'Cadastro Concluído' not in tags:
            tags.append('Cadastro Concluído')
        verso.tags_adicionar = tags
        verso.historico_status_apos_sucesso = 'cadastro_concluido'
        verso.historico_observacoes_template = 'Cadastro 100% — todos os docs recebidos, aguardando atendente'
        verso.msg_sucesso = 'Tudo pronto! ##2705## Vou te transferir pra um atendente finalizar.'
        verso.save()
        print('  ✓ documentacao_verso_doc: status_api=pendente + tag Cadastro Concluído')


def reverter(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    c = RegraValidacao.objects.filter(question_id='confirmacao_dados').first()
    if c:
        c.status_api_apos_sucesso = 'aguardando_assinatura'
        c.save()
    v = RegraValidacao.objects.filter(question_id='documentacao_verso_doc').first()
    if v:
        v.status_api_apos_sucesso = ''
        v.save()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0009_o_que_ajustar'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
