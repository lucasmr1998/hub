"""Simplifica o fluxo pós-documentos: turno → data → abertura automática.

Antes:
  docs aprovados → escolha_turno → escolha_data → confirmacao_agendamento
                                                 → engine dispara abertura

Agora:
  docs aprovados → escolha_turno → escolha_data → engine dispara abertura
                                                 → status='instalacao_agendada'

A regra `confirmacao_agendamento` continua existindo (não é apagada pra evitar
quebrar fluxos antigos), mas não é mais referenciada na sequência da API IA
(`onboarding.SEQUENCIA_COLETA`).

Ajustes:
- escolha_data: passa a setar status_api_apos_sucesso='instalacao_agendada'
  + tag 'Instalação Agendada' + historico. msg_sucesso fica vazio porque o
  engine sobrescreve dinamicamente com os dados retornados pelo agendamento
  (data/turno/horário/técnico).
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')

    data = Regra.objects.filter(question_id='escolha_data').first()
    if data:
        data.status_api_apos_sucesso = 'instalacao_agendada'
        tags = list(data.tags_adicionar or [])
        if 'Instalação Agendada' not in tags:
            tags.append('Instalação Agendada')
        data.tags_adicionar = tags
        data.historico_status_apos_sucesso = 'instalacao_agendada'
        data.historico_observacoes_template = (
            'Agendamento confirmado: data={extracted[data_instalacao_label]} '
            'turno={extracted[turno_instalacao]}'
        )
        # msg_sucesso fica vazio — o engine sobrescreve com a resposta do
        # serviço de agendamento (com horário, técnico, número da OS, etc).
        data.msg_sucesso = ''
        data.save()
        print('  ✓ escolha_data: status_api=instalacao_agendada + tag adicionada')


def reverter(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    d = Regra.objects.filter(question_id='escolha_data').first()
    if d:
        d.status_api_apos_sucesso = ''
        d.tags_adicionar = []
        d.historico_status_apos_sucesso = 'data_escolhida'
        d.historico_observacoes_template = 'Data instalação: {extracted[data_instalacao]}'
        d.msg_sucesso = 'Data anotada! ##1f4c5## Só pra confirmar...'
        d.save()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0013_menu_cliente_existente'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
