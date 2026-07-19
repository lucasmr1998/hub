"""Sincroniza as regras de validação com o texto EXATO das perguntas do flow.json.

- Atualiza `pergunta_padrao` das regras existentes pro texto literal do Matrix
- Adiciona regras NOVAS detectadas no flow (coleta_uf, escolhas de URA)
- A inferência por keywords no client.py continua sendo o caminho principal,
  mas o match exato via pergunta_padrao funciona como fallback rápido.
"""
from django.db import migrations


PERGUNTAS_FLOW = {
    'coleta_nome': (
        'Oi! Que bom ter você aqui na {#nome_empresa} Internet ##1f680##\n\n'
        'Para começarmos, qual é o seu nome?\n'
    ),
    'coleta_cidade': 'Para qual a cidade que solicita atendimento?',
    'coleta_rua': 'Qual é o nome da sua rua?',
    'coleta_bairro': 'Qual é o bairro?',
    'coleta_cep': 'Digite o seu CEP. ##1f3e0##\n(Exemplo: XXXXX-XXX)',
    'coleta_numero': (
        'Certo! Agora digite apenas o número do endereço, sem o complemento:\n'
        '(Exemplo: N° 99)\n\nSe for uma residência sem número, envie s/n.'
    ),
    'coleta_ponto_referencia': (
        'Só pra ajudar nosso time na instalação ##263A##\n\n'
        'Tem algum ponto de referência perto da sua casa que você possa me informar?\n\n'
    ),
    'coleta_data_nascimento': 'Informe sua data de nascimento.\n(No formato: 01/01/2000)',
    'coleta_cpf': (
        '{#CONTATO.NOME}, é bem rapidinho ##263A##\n'
        'Para dar continuidade ao atendimento, pode me informar seu CPF?\n'
        '(Exemplo: 999.999.999-99)'
    ),
    'coleta_email': 'Pode me informar seu e-mail, por favor? ##263A##\n(Exemplo: exemplo@email.com)',
    'coleta_rg': 'Agora, digite o número do seu RG.\n',
    'documentacao_selfie': (
        'Pode começar enviando uma selfie segurando seu documento de identidade '
        'ao lado do rosto, por favor.'
    ),
    'documentacao_frente_doc': (
        'Em seguida, precisamos da foto da frente do documento, '
        'garantindo que todas as informações estejam legíveis.'
    ),
    'documentacao_verso_doc': 'Última etapa: precisamos da foto da parte de trás do seu RG/CNH',
}

# Regras NOVAS detectadas no flow que não existem na seed inicial
REGRAS_NOVAS = [
    {
        'question_id': 'coleta_uf', 'ordem': 65,
        'pergunta_padrao': 'Olá! Poderia me informar qual é a UF (sigla do estado) onde você reside?\nExemplo: PI, MA, CE.',
        'descricao': 'Fallback de UF se ViaCEP não retornou o estado',
        'extractor_tipo': 'texto_livre',
        'instrucoes_ia': 'Extraia a sigla do estado (UF) em 2 letras maiúsculas. Se cliente disser nome completo, converta. Ex: "Piauí" → "PI".',
        'campo_lead_atualizar': 'estado',
        'msg_erro': 'Pode me passar só a sigla do estado? Exemplo: PI, MA, CE.',
    },
    {
        'question_id': 'escolha_canal_contratacao', 'ordem': 25,
        'pergunta_padrao': 'Ótimo, {#CONTATO.NOME}!\nA contratação é rápida e 100% segura.\nPrefere contratar pelo site ou continuar com nosso time aqui no WhatsApp?',
        'descricao': 'URA ura_8 — Seguir WhatsApp ou Contratar pelo Site',
        'extractor_tipo': 'opcao',
        'extractor_config': {'opcoes': {
            'whatsapp': ['1', 'whatsapp', 'whats', 'aqui', 'seguir'],
            'site': ['2', 'site', 'link', 'web'],
        }},
        'msg_erro': 'Pode escolher 1 (WhatsApp) ou 2 (Site)?',
    },
    {
        'question_id': 'escolha_plano_contratar', 'ordem': 55,
        'pergunta_padrao': 'Contratar esse Plano',
        'descricao': 'URA ura_plano — confirma plano apresentado ou pede mais opções',
        'extractor_tipo': 'opcao',
        'extractor_config': {'opcoes': {
            'contratar': ['1', 'contratar', 'quero', 'aceito'],
            'mais_opcoes': ['2', 'mais', 'outras', 'opções', 'opcoes'],
        }},
    },
    {
        'question_id': 'escolha_plano_alternativo', 'ordem': 56,
        'pergunta_padrao': 'Ótimo, pois temos os seguintes planos disponíveis com mais velocidade e ainda mais benefícios para você.',
        'descricao': 'URA ura_plano_2 — Turbo / Energia / Rastreamento / voltar',
        'extractor_tipo': 'opcao',
        'extractor_config': {'opcoes': {
            'turbo': ['1', 'turbo', '1gb'],
            'energia': ['2', 'energia', 'luz'],
            'rastreamento': ['3', 'rastreamento', 'rastreio', 'veículo'],
            'voltar': ['4', 'voltar', 'menu'],
        }},
    },
    {
        'question_id': 'confirmacao_endereco', 'ordem': 45,
        'pergunta_padrao': 'Confirme seu endereço:\n\nCEP: {#ret_cep}  \nEstado: {#ret_estado}  \nCidade: {#ret_cidade}  \nBairro: {#ret_bairro}  \nRua: {#ret_rua}\n\nPosso seguir com esses dados? ',
        'descricao': 'URA ura_7 — confirma endereço retornado pelo ViaCEP',
        'extractor_tipo': 'opcao',
        'extractor_config': {'opcoes': {
            'corretos': ['1', 'sim', 'corretos', 'certo', 'pode'],
            'corrigir': ['2', 'não', 'nao', 'corrigir', 'errado'],
        }},
    },
]


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')

    # 1. Atualizar pergunta_padrao das regras existentes
    atualizadas = 0
    for qid, texto in PERGUNTAS_FLOW.items():
        try:
            r = RegraValidacao.objects.get(question_id=qid)
            r.pergunta_padrao = texto
            r.save(update_fields=['pergunta_padrao'])
            atualizadas += 1
        except RegraValidacao.DoesNotExist:
            print(f'  ⚠ regra {qid!r} não existe — pulando')

    # 2. Criar regras novas
    criadas = 0
    for regra in REGRAS_NOVAS:
        _, created = RegraValidacao.objects.update_or_create(
            question_id=regra['question_id'],
            defaults=regra,
        )
        if created:
            criadas += 1

    print(f'  ✓ {atualizadas} regras atualizadas, {criadas} regras novas criadas')


def reverter(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    # Remove apenas as novas; pergunta_padrao não dá pra reverter (sem snapshot)
    qids_novos = [r['question_id'] for r in REGRAS_NOVAS]
    RegraValidacao.objects.filter(question_id__in=qids_novos).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0002_seed_regras_megalink'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
