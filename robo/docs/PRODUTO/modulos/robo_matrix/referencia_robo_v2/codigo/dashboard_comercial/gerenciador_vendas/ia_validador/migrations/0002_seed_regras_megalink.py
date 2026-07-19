"""Seed das 22 regras do fluxo de vendas Megalink."""
from django.db import migrations


REGRAS_SEED = [
    {
        'question_id': 'cumprimento', 'ordem': 10,
        'pergunta_padrao': 'Oi! Eu sou a Aurora, da Megalink. Como posso te ajudar hoje?',
        'descricao': 'Cumprimento inicial — detecta intent (contratar/suporte/cancelar)',
        'extractor_tipo': 'texto_livre',
        'instrucoes_ia': (
            'Identifique a intenção do cliente. Possíveis intents: '
            '"contratar" (cliente quer internet), "suporte" (tem problema técnico), '
            '"cancelar" (quer cancelar), "duvida" (quer info), "desistir" (não quer mais).'
        ),
        'historico_status_apos_sucesso': 'fluxo_inicializado',
        'historico_observacoes_template': 'Cliente iniciou: {answer}',
        'msg_sucesso': 'Que bom! Vamos te ajudar.',
    },
    {
        'question_id': 'tipo_imovel', 'ordem': 20,
        'pergunta_padrao': 'A internet será para sua casa ou para sua empresa?',
        'descricao': 'Roteia entre fluxo residencial ou empresarial',
        'extractor_tipo': 'opcao',
        'extractor_config': {'opcoes': {'casa': ['casa', 'residencial', 'residência', '1'],
                                         'empresa': ['empresa', 'comercial', 'negócio', '2']}},
        'msg_erro': 'Pode escolher: casa ou empresa?',
    },
    {
        'question_id': 'coleta_cidade', 'ordem': 30,
        'pergunta_padrao': 'Em qual cidade você mora?',
        'descricao': 'Coleta cidade — verifica cobertura',
        'extractor_tipo': 'texto_livre',
        'instrucoes_ia': 'Extraia o nome da cidade. Verifique se está no Piauí (cobertura Megalink). dados_extraidos: {cidade, estado}',
        'campo_lead_atualizar': 'cidade',
        'msg_erro': 'Pode me dizer só o nome da sua cidade?',
    },
    {
        'question_id': 'coleta_cep', 'ordem': 40,
        'pergunta_padrao': 'Você pode me passar o CEP da sua residência? (Exemplo: 64000-000)',
        'descricao': 'CEP com ViaCEP — preenche endereço inteiro',
        'extractor_tipo': 'cep',
        'tags_adicionar': ['Endereço'],
        'msg_sucesso': 'Perfeito! Anotei seu endereço.',
        'msg_erro': 'Esse CEP parece incorreto. Pode conferir? São 8 dígitos.',
    },
    {
        'question_id': 'coleta_rua', 'ordem': 50,
        'pergunta_padrao': 'Qual o nome da sua rua?',
        'descricao': 'Fallback de rua se CEP falhou',
        'extractor_tipo': 'texto_livre',
        'campo_lead_atualizar': 'rua',
    },
    {
        'question_id': 'coleta_bairro', 'ordem': 60,
        'pergunta_padrao': 'Qual o bairro?',
        'extractor_tipo': 'texto_livre',
        'campo_lead_atualizar': 'bairro',
    },
    {
        'question_id': 'coleta_numero', 'ordem': 70,
        'pergunta_padrao': 'Qual o número da residência? (Se for sem número, envie S/N)',
        'extractor_tipo': 'numero',
        'campo_lead_atualizar': 'numero_residencia',
    },
    {
        'question_id': 'coleta_ponto_referencia', 'ordem': 80,
        'pergunta_padrao': 'Tem algum ponto de referência perto da sua casa?',
        'extractor_tipo': 'texto_livre',
        'campo_lead_atualizar': 'ponto_referencia',
        'permite_pular': True,
    },
    {
        'question_id': 'coleta_nome', 'ordem': 90,
        'pergunta_padrao': 'Pra continuar, qual seu nome completo?',
        'extractor_tipo': 'nome',
        'campo_lead_atualizar': 'nome_razaosocial',
        'tags_adicionar': ['Comercial'],
        'msg_erro': 'Preciso do nome completo, com sobrenome.',
    },
    {
        'question_id': 'coleta_cpf', 'ordem': 100,
        'pergunta_padrao': 'Agora me passa seu CPF, por favor. (Exemplo: 999.999.999-99)',
        'extractor_tipo': 'cpf',
        'campo_lead_atualizar': 'cpf_cnpj',
        'tags_adicionar': ['Documental'],
        'msg_erro': 'Esse CPF está incorreto. Pode conferir e mandar de novo?',
        'max_tentativas': 3,
    },
    {
        'question_id': 'coleta_rg', 'ordem': 110,
        'pergunta_padrao': 'Agora me passa seu RG, por favor.',
        'extractor_tipo': 'texto_livre',
        'instrucoes_ia': 'Aceite RG em qualquer formato. Se cliente disser "não tem" / "depois", aceitar com rg="".',
        'campo_lead_atualizar': 'rg',
        'permite_pular': True,
    },
    {
        'question_id': 'coleta_data_nascimento', 'ordem': 120,
        'pergunta_padrao': 'Informe sua data de nascimento. (No formato: 01/01/2000)',
        'extractor_tipo': 'data_nascimento',
        'campo_lead_atualizar': 'data_nascimento',
        'msg_erro': 'Pode me passar no formato dia/mês/ano? Ex: 15/03/1990',
    },
    {
        'question_id': 'coleta_email', 'ordem': 130,
        'pergunta_padrao': 'Pode me informar seu e-mail, por favor?',
        'extractor_tipo': 'email',
        'campo_lead_atualizar': 'email',
        'permite_pular': True,
    },
    {
        'question_id': 'escolha_plano', 'ordem': 140,
        'pergunta_padrao': 'Temos planos de 300MB, 620MB, 1 Giga e 2 Giga. Qual te interessa?',
        'extractor_tipo': 'opcao',
        'extractor_config': {
            'opcoes': {
                '1647': ['300', '300mb', '300 mega'],
                '1649': ['620', '620mb', '620 mega'],
                '1648': ['1g', '1giga', '1 giga', '1000', 'turbo'],
                '1650': ['2g', '2giga', '2 giga', '2000'],
            },
            'descricao_opcoes': {
                '1647': 'Plano de 300MB (R$ 79,90)',
                '1649': 'Plano de 620MB (R$ 99,90)',
                '1648': 'Plano de 1GB Turbo (R$ 129,90)',
                '1650': 'Plano de 2GB (R$ 169,90)',
            },
        },
        'campo_lead_atualizar': 'id_plano_rp',
        'msg_erro': 'As opções são: 300MB, 620MB, 1 Giga ou 2 Giga.',
    },
    {
        'question_id': 'dia_vencimento', 'ordem': 150,
        'pergunta_padrao': 'Qual dia do mês prefere para vencimento da fatura? (5, 10, 15, 20 ou 25)',
        'extractor_tipo': 'opcao',
        'extractor_config': {
            'opcoes': {
                '9': ['5'],
                '5': ['10', '15'],
                '6': ['20', '25'],
                '28': ['1'],
            },
        },
        'campo_lead_atualizar': 'id_dia_vencimento',
        'msg_erro': 'Os dias disponíveis são: 5, 10, 15, 20 ou 25.',
    },
    {
        'question_id': 'confirmacao_dados', 'ordem': 160,
        'pergunta_padrao': 'Confirme seus dados, por favor. Está tudo certo?',
        'descricao': 'Confirmação final antes de pedir documentação',
        'extractor_tipo': 'confirmacao',
        'status_api_apos_sucesso': 'aguardando_assinatura',
        'tags_adicionar': ['Assinado'],
        'msg_sucesso': 'Perfeito! Vamos pra próxima etapa.',
    },
    {
        'question_id': 'documentacao_selfie', 'ordem': 170,
        'pergunta_padrao': 'Selfie sua segurando seu documento de identidade ao lado do rosto.',
        'extractor_tipo': 'imagem',
        'descricao_imagem': 'selfie_com_doc',
        'msg_sucesso': 'Recebi! Agora a foto da frente do seu documento.',
        'msg_erro': 'Preciso de uma foto sua segurando o documento. Pode mandar?',
    },
    {
        'question_id': 'documentacao_frente_doc', 'ordem': 180,
        'pergunta_padrao': 'Foto da frente do seu documento (RG ou CNH).',
        'extractor_tipo': 'imagem',
        'descricao_imagem': 'frente_doc',
        'msg_sucesso': 'Recebi! Agora a foto da parte de trás.',
    },
    {
        'question_id': 'documentacao_verso_doc', 'ordem': 190,
        'pergunta_padrao': 'Foto da parte de trás do seu RG/CNH.',
        'extractor_tipo': 'imagem',
        'descricao_imagem': 'verso_doc',
        'msg_sucesso': 'Pronto! Recebi tudo. Vou validar sua documentação.',
    },
    {
        'question_id': 'escolha_turno', 'ordem': 200,
        'pergunta_padrao': 'Para a instalação, qual é o melhor período: manhã ou tarde?',
        'extractor_tipo': 'opcao',
        'extractor_config': {'opcoes': {'manha': ['manhã', 'manha', '1'], 'tarde': ['tarde', '2']}},
        'msg_erro': 'Pode escolher: manhã ou tarde?',
    },
    {
        'question_id': 'escolha_data', 'ordem': 210,
        'pergunta_padrao': 'Escolha a melhor data para instalação: 1, 2 ou 3.',
        'extractor_tipo': 'opcao',
        'extractor_config': {'opcoes': {'1': ['1', 'primeira'], '2': ['2', 'segunda'], '3': ['3', 'terceira']}},
        'msg_erro': 'Pode escolher uma das 3 datas: 1, 2 ou 3?',
    },
    {
        'question_id': 'confirmacao_agendamento', 'ordem': 220,
        'pergunta_padrao': 'Sua instalação foi agendada. Mais alguma dúvida?',
        'extractor_tipo': 'confirmacao',
        'status_api_apos_sucesso': 'pendente',
        'historico_status_apos_sucesso': 'fluxo_finalizado',
        'historico_observacoes_template': 'Agendamento confirmado: {answer}',
        'msg_sucesso': 'Obrigada pela escolha! Nossa equipe vai te procurar.',
    },
]


def criar_regras(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    for dados in REGRAS_SEED:
        Regra.objects.update_or_create(
            question_id=dados['question_id'],
            defaults=dados,
        )


def remover_regras(apps, schema_editor):
    Regra = apps.get_model('ia_validador', 'RegraValidacao')
    Regra.objects.filter(question_id__in=[r['question_id'] for r in REGRAS_SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ia_validador', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(criar_regras, reverse_code=remover_regras),
    ]
