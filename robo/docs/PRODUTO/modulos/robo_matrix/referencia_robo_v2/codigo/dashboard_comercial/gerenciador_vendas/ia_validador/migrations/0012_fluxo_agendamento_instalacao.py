"""Estrutura o fluxo final de agendamento (turno + data + confirmação).

Antes: ao receber o verso do doc, o bot setava status='pendente' e
transbordava direto pra atendente humano — o fluxo de turno/data
existente no Matrix nunca era alcançado.

Agora: o verso só conclui a documentação. Em seguida o bot pergunta
turno (manhã/tarde), recebe a escolha da data (1/2/3 das datas que
o Matrix consultou via api_25), confirma com o cliente e SÓ ENTÃO
seta status='instalacao_agendada' + transborda pra atendente fechar
contrato no Hubsoft.

Regras ajustadas:
- documentacao_verso_doc: remove status='pendente' (não bloqueia mais)
- escolha_turno: msg conduz pro próximo passo (mostrar datas)
- escolha_data: salva data REAL no campo (engine mapeia opção→data)
- confirmacao_agendamento: vira confirmação real (sim/não), só com
  'sim' seta status='instalacao_agendada' + tags + finaliza fluxo
"""
from django.db import migrations


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')

    # ── 1) Verso do doc: não bloqueia mais o fluxo ──────────────────────
    verso = RegraValidacao.objects.filter(question_id='documentacao_verso_doc').first()
    if verso:
        verso.status_api_apos_sucesso = ''   # antes era 'pendente'
        verso.msg_sucesso = (
            'Documentação completa! ##2705##\n\n'
            'Agora vamos agendar sua instalação. ##1f4c5##'
        )
        verso.save()
        print('  ✓ documentacao_verso_doc: status_api zerado, msg encaminha pro agendamento')

    # ── 2) Escolha do turno: conduz pra etapa seguinte ──────────────────
    turno = RegraValidacao.objects.filter(question_id='escolha_turno').first()
    if turno:
        turno.pergunta_padrao = (
            'Pra instalação, qual o melhor turno pra você?\n\n'
            '1) Manhã (08:00 às 12:00)\n'
            '2) Tarde (13:00 às 17:00)'
        )
        turno.extractor_config = {
            'opcoes': {
                'manha': ['manhã', 'manha', '1', 'manhãs', 'manhas', 'pela manha'],
                'tarde': ['tarde', '2', 'pela tarde', 'a tarde'],
            }
        }
        turno.campo_lead_atualizar = 'turno_instalacao'
        turno.msg_sucesso = 'Turno anotado! ##2705## Agora vou te mostrar as datas disponíveis.'
        turno.msg_erro = 'Pode escolher? *1* pra manhã ou *2* pra tarde.'
        turno.historico_status_apos_sucesso = 'turno_escolhido'
        turno.historico_observacoes_template = 'Turno escolhido: {extracted[turno_instalacao]}'
        turno.save()
        print('  ✓ escolha_turno: extractor + mensagens atualizadas')

    # ── 3) Escolha da data: engine resolve opção (1/2/3) → data real ────
    data = RegraValidacao.objects.filter(question_id='escolha_data').first()
    if data:
        data.pergunta_padrao = (
            'Essas são as próximas datas disponíveis pra instalação:\n\n'
            '1) {data_instalacao_1}\n'
            '2) {data_instalacao_2}\n'
            '3) {data_instalacao_3}\n\n'
            'Qual prefere?'
        )
        data.extractor_config = {
            'opcoes': {
                '1': ['1', 'primeira', 'um'],
                '2': ['2', 'segunda', 'dois'],
                '3': ['3', 'terceira', 'tres', 'três'],
            }
        }
        data.campo_lead_atualizar = 'data_instalacao'
        data.msg_sucesso = 'Data anotada! ##1f4c5## Só pra confirmar...'
        data.msg_erro = 'Pode escolher *1*, *2* ou *3* pra uma das datas?'
        data.historico_status_apos_sucesso = 'data_escolhida'
        data.historico_observacoes_template = 'Data instalação: {extracted[data_instalacao]}'
        data.save()
        print('  ✓ escolha_data: extractor configurado (engine mapeia op→data)')

    # ── 4) Confirmação final: SIM agenda, NÃO volta pra turno ───────────
    conf = RegraValidacao.objects.filter(question_id='confirmacao_agendamento').first()
    if conf:
        conf.pergunta_padrao = (
            'Confirma sua instalação?\n\n'
            'Turno: {turno_instalacao}\n'
            'Data: {data_instalacao}\n\n'
            '1) Sim, confirmo\n'
            '2) Não, quero alterar'
        )
        conf.extractor_tipo = 'confirmacao'
        conf.campo_lead_atualizar = ''   # confirmação só dispara status
        conf.status_api_apos_sucesso = 'instalacao_agendada'
        conf.tags_adicionar = ['Instalação Agendada']
        conf.historico_status_apos_sucesso = 'instalacao_agendada'
        conf.historico_observacoes_template = (
            'Cliente confirmou agendamento: turno={turno_instalacao} data={data_instalacao}'
        )
        conf.msg_sucesso = (
            'Instalação agendada! ##2705##\n\n'
            'Nossa equipe vai até você no turno e data combinados. '
            'Vou te transferir pra um atendente finalizar o contrato.'
        )
        conf.msg_erro = 'Pode confirmar? *1* pra sim ou *2* pra alterar.'
        conf.save()
        print('  ✓ confirmacao_agendamento: confirmação real (sim/não)')


def reverter(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')

    verso = RegraValidacao.objects.filter(question_id='documentacao_verso_doc').first()
    if verso:
        verso.status_api_apos_sucesso = 'pendente'
        verso.save()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0011_ponto_referencia_estruturado'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
