"""Preenche os campos de AÇÕES (campo_lead, status, tags, histórico, imagem)
e MENSAGENS (sucesso, erro, max_tentativas) de TODAS as regras de validação.

Após esta migration, cada regra fica autocontida: quando a API IA valida com
sucesso, ela sabe exatamente o que atualizar no lead Django e qual mensagem
enviar de volta pro Matrix.
"""
from django.db import migrations


CONFIGS = {
    # ─────────── INÍCIO DO FLUXO ───────────────────────────────────────
    'cumprimento': {
        'historico_status_apos_sucesso': 'fluxo_inicializado',
        'historico_observacoes_template': 'Cliente iniciou contato: "{answer}"',
        'tags_adicionar': ['Lead Novo'],
        'msg_sucesso': 'Que bom! Vamos te ajudar.',
        'msg_erro': 'Pode me dizer como posso te ajudar hoje?',
    },
    'tipo_imovel': {
        'campo_lead_atualizar': 'tipo_imovel',
        'msg_sucesso': 'Perfeito! ##263A##',
        'msg_erro': 'Pode escolher: 1 - Casa ou 2 - Empresa?',
        'msg_max_tentativas': 'Vou te transferir pra um atendente pra ajudar com isso.',
        'forcar_transbordo_apos_max': True,
    },
    'escolha_canal_contratacao': {
        'historico_status_apos_sucesso': 'canal_escolhido',
        'historico_observacoes_template': 'Cliente escolheu: {answer}',
        'msg_sucesso': '',
        'msg_erro': 'Por favor, escolha 1 (WhatsApp) ou 2 (Site).',
    },

    # ─────────── COLETA DE ENDEREÇO ────────────────────────────────────
    'coleta_cidade': {
        'campo_lead_atualizar': 'cidade',
        'tags_adicionar': ['Endereço'],
        'msg_sucesso': 'Anotei sua cidade!',
        'msg_erro': 'Pode me dizer só o nome da sua cidade?',
        'msg_max_tentativas': 'Não consegui entender. Vou pedir ajuda pra um atendente.',
        'forcar_transbordo_apos_max': True,
    },
    'coleta_cep': {
        'campo_lead_atualizar': 'cep',
        'tags_adicionar': ['Endereço'],
        'historico_status_apos_sucesso': 'cep_validado',
        'historico_observacoes_template': 'CEP {extracted}: {answer}',
        'msg_sucesso': 'Endereço encontrado! ##263A##',
        'msg_erro': 'Esse CEP parece incorreto. Pode conferir? São 8 dígitos (Ex: 64000-000).',
        'msg_max_tentativas': 'Vou anotar manualmente. Me ajude com algumas infos.',
    },
    'coleta_rua': {
        'campo_lead_atualizar': 'rua',
        'msg_sucesso': 'Anotei sua rua!',
        'msg_erro': 'Pode me dizer o nome da rua?',
    },
    'coleta_bairro': {
        'campo_lead_atualizar': 'bairro',
        'msg_sucesso': 'Beleza!',
        'msg_erro': 'Pode me dizer o bairro?',
    },
    'coleta_uf': {
        'campo_lead_atualizar': 'estado',
        'msg_sucesso': 'Estado anotado!',
        'msg_erro': 'Me passe só a sigla, exemplo: PI, MA, CE.',
    },
    'coleta_numero': {
        'campo_lead_atualizar': 'numero_residencia',
        'msg_sucesso': 'Número anotado!',
        'msg_erro': 'Digite apenas o número (ex: 99) ou S/N se não tiver.',
    },
    'coleta_ponto_referencia': {
        'campo_lead_atualizar': 'ponto_referencia',
        'permite_pular': True,
        'msg_sucesso': 'Anotado, vai ajudar bastante! ##263A##',
        'msg_erro': 'Pode descrever um ponto próximo (mercado, escola, etc)?',
    },
    'confirmacao_endereco': {
        'historico_status_apos_sucesso': 'endereco_confirmado',
        'historico_observacoes_template': 'Endereço confirmado pelo cliente',
        'msg_sucesso': '',
        'msg_erro': 'Por favor escolha 1 (corretos) ou 2 (corrigir).',
    },

    # ─────────── DADOS PESSOAIS ────────────────────────────────────────
    'coleta_nome': {
        'campo_lead_atualizar': 'nome_razaosocial',
        'tags_adicionar': ['Comercial'],
        'msg_sucesso': 'Perfeito, {extracted[nome_razaosocial]}! ##263A##',
        'msg_erro': 'Preciso do nome completo (nome + sobrenome).',
        'msg_max_tentativas': 'Vou continuar e nosso time confirma depois.',
    },
    'coleta_cpf': {
        'campo_lead_atualizar': 'cpf_cnpj',
        'tags_adicionar': ['Comercial', 'CPF Validado'],
        'historico_status_apos_sucesso': 'cpf_validado',
        'historico_observacoes_template': 'CPF do cliente: {extracted}',
        'msg_sucesso': 'CPF validado! ##263A##',
        'msg_erro': 'CPF inválido. Pode conferir? (Exemplo: 999.999.999-99)',
        'msg_max_tentativas': 'CPF incorreto após várias tentativas. Vou transferir pra um atendente.',
        'forcar_transbordo_apos_max': True,
    },
    'coleta_rg': {
        'campo_lead_atualizar': 'rg',
        'msg_sucesso': 'RG anotado!',
        'msg_erro': 'Digite somente os números do seu RG.',
    },
    'coleta_data_nascimento': {
        'campo_lead_atualizar': 'data_nascimento',
        'msg_sucesso': 'Anotado!',
        'msg_erro': 'Digite no formato 01/01/2000. Lembre que você deve ter 18+.',
        'msg_max_tentativas': 'Não consegui validar sua idade. Vou transferir pra um atendente.',
        'forcar_transbordo_apos_max': True,
    },
    'coleta_email': {
        'campo_lead_atualizar': 'email',
        'msg_sucesso': 'E-mail anotado!',
        'msg_erro': 'E-mail parece incorreto. Pode conferir? (Ex: nome@exemplo.com)',
    },

    # ─────────── PLANO E PAGAMENTO ─────────────────────────────────────
    'escolha_plano': {
        'campo_lead_atualizar': 'id_plano_rp',
        'tags_adicionar': ['Plano Escolhido'],
        'historico_status_apos_sucesso': 'plano_selecionado',
        'historico_observacoes_template': 'Plano escolhido: {answer}',
        'msg_sucesso': 'Excelente escolha! ##1f680##',
        'msg_erro': 'Pode escolher uma das opções listadas?',
    },
    'escolha_plano_contratar': {
        'historico_status_apos_sucesso': 'plano_confirmado',
        'historico_observacoes_template': 'Cliente: {answer}',
        'msg_sucesso': '',
        'msg_erro': 'Por favor escolha: 1 (Contratar) ou 2 (Mais opções).',
    },
    'escolha_plano_alternativo': {
        'historico_status_apos_sucesso': 'plano_alternativo_escolhido',
        'historico_observacoes_template': 'Escolha alternativa: {answer}',
        'msg_sucesso': '',
        'msg_erro': 'Por favor escolha uma das opções (1 a 4).',
    },
    'dia_vencimento': {
        'campo_lead_atualizar': 'id_dia_vencimento',
        'msg_sucesso': 'Dia de vencimento anotado!',
        'msg_erro': 'Pode escolher uma das datas: 1, 5, 15 ou 20?',
    },

    # ─────────── CONFIRMAÇÃO + STATUS ──────────────────────────────────
    'confirmacao_dados': {
        'status_api_apos_sucesso': 'aguardando_assinatura',
        'tags_adicionar': ['Dados Confirmados'],
        'historico_status_apos_sucesso': 'dados_confirmados',
        'historico_observacoes_template': 'Cliente confirmou todos os dados',
        'msg_sucesso': 'Tudo certo! Vamos pro próximo passo.',
        'msg_erro': 'Por favor responda: 1 (Concluir) para finalizar.',
    },

    # ─────────── DOCUMENTAÇÃO (IMAGENS) ────────────────────────────────
    'documentacao_selfie': {
        'descricao_imagem': 'selfie_com_doc',
        'tags_adicionar': ['Documentação'],
        'historico_status_apos_sucesso': 'doc_selfie_enviada',
        'msg_sucesso': 'Selfie recebida! ##263A##',
        'msg_erro': 'Não recebi a foto. Pode enviar uma selfie segurando o documento ao lado do rosto?',
        'msg_max_tentativas': 'Vou continuar e nosso time validará a foto depois.',
    },
    'documentacao_frente_doc': {
        'descricao_imagem': 'frente_doc',
        'historico_status_apos_sucesso': 'doc_frente_enviada',
        'msg_sucesso': 'Foto da frente recebida!',
        'msg_erro': 'Preciso da foto da FRENTE do seu documento. Pode tirar de novo?',
        'msg_max_tentativas': 'Vou continuar e nosso time validará depois.',
    },
    'documentacao_verso_doc': {
        'descricao_imagem': 'verso_doc',
        'status_api_apos_sucesso': 'pendente',
        'tags_adicionar': ['Assinado', 'Docs Completos'],
        'historico_status_apos_sucesso': 'fluxo_finalizado',
        'historico_observacoes_template': 'Documentação completa enviada — pronto pra Hubsoft',
        'msg_sucesso': 'Documentação completa! ##1f680## Finalizamos sua contratação.',
        'msg_erro': 'Preciso da foto do VERSO do documento. Pode enviar?',
        'msg_max_tentativas': 'Vou seguir e nosso time validará as fotos.',
    },

    # ─────────── INSTALAÇÃO (HUBSOFT) ──────────────────────────────────
    'escolha_turno': {
        'campo_lead_atualizar': 'turno_instalacao',
        'historico_status_apos_sucesso': 'turno_escolhido',
        'historico_observacoes_template': 'Turno escolhido: {answer}',
        'msg_sucesso': 'Turno anotado!',
        'msg_erro': 'Por favor escolha 1 (Manhã) ou 2 (Tarde).',
    },
    'escolha_data': {
        'campo_lead_atualizar': 'data_instalacao',
        'historico_status_apos_sucesso': 'data_escolhida',
        'historico_observacoes_template': 'Data instalação: {answer}',
        'msg_sucesso': 'Data agendada!',
        'msg_erro': 'Por favor escolha uma das datas disponíveis (1, 2 ou 3).',
    },
    'confirmacao_agendamento': {
        'status_api_apos_sucesso': 'instalacao_agendada',
        'tags_adicionar': ['Instalação Agendada'],
        'historico_status_apos_sucesso': 'instalacao_agendada',
        'historico_observacoes_template': 'Cliente confirmou agendamento: {answer}',
        'msg_sucesso': 'Agendamento confirmado! Nossa equipe vai até você. ##1f680##',
        'msg_erro': 'Por favor confirme: 1 (Sim) ou 2 (Reagendar).',
    },
}


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')

    atualizadas = 0
    pulados = []
    for qid, campos in CONFIGS.items():
        try:
            r = RegraValidacao.objects.get(question_id=qid)
            for k, v in campos.items():
                setattr(r, k, v)
            r.save()
            atualizadas += 1
        except RegraValidacao.DoesNotExist:
            pulados.append(qid)

    print(f'  ✓ {atualizadas}/{len(CONFIGS)} regras preenchidas com ações + mensagens')
    if pulados:
        print(f'  ⚠ {len(pulados)} regras não existem (precisam ser criadas antes): {pulados}')


def reverter(apps, schema_editor):
    """Reset dos campos para vazio."""
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    campos_reset = {
        'campo_lead_atualizar': '',
        'status_api_apos_sucesso': '',
        'tags_adicionar': [],
        'tags_remover': [],
        'historico_status_apos_sucesso': '',
        'historico_observacoes_template': '',
        'descricao_imagem': '',
        'msg_sucesso': '',
        'msg_erro': '',
        'msg_max_tentativas': '',
        'forcar_transbordo_apos_max': False,
    }
    qids = list(CONFIGS.keys())
    RegraValidacao.objects.filter(question_id__in=qids).update(**campos_reset)


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0003_sync_perguntas_flow_json'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
