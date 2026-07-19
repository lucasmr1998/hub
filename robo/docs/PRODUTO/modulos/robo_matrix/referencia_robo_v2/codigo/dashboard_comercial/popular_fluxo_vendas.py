"""
Script para popular o fluxo de vendas com questões inteligentes
Executar: python manage.py shell < popular_fluxo_vendas.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings')
django.setup()

from vendas_web.models import (
    FluxoAtendimento, 
    QuestaoFluxo,
    PlanoInternet
)
from django.utils import timezone

def criar_fluxo_vendas():
    """Cria o fluxo de vendas completo com todas as questões"""
    
    print("🚀 Iniciando criação do Fluxo de Vendas...")
    
    # 1. Criar ou buscar o fluxo principal
    fluxo, created = FluxoAtendimento.objects.get_or_create(
        nome="Fluxo de Vendas - Internet Residencial",
        defaults={
            'descricao': 'Fluxo completo de vendas para contratação de planos de internet',
            'tipo_fluxo': 'vendas',
            'status': 'ativo',
            'max_tentativas': 3,
            'tempo_limite_minutos': 30,
            'permite_pular_questoes': False,
            'ativo': True,
            'criado_por': 'Sistema'
        }
    )
    
    if created:
        print(f"✅ Fluxo criado: {fluxo.nome}")
    else:
        print(f"ℹ️  Fluxo já existe: {fluxo.nome}")
        # Limpar questões antigas para recriar
        fluxo.questoes.all().delete()
        print("🗑️  Questões antigas removidas")
    
    # 2. QUESTÃO 1: Nome do cliente
    q1 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=1,
        titulo="Olá! Tudo bem? Para começarmos, qual o seu nome, por favor?",
        descricao="Primeira questão para capturar o nome do cliente",
        tipo_questao='texto',
        tipo_validacao='obrigatoria',
        tamanho_minimo=3,
        tamanho_maximo=100,
        mensagem_erro_padrao="Por favor, digite seu nome completo.",
        instrucoes_resposta_correta="Digite apenas letras e espaços.",
        regex_validacao=r'^[A-Za-zÀ-ÿ\s]+$',
        max_tentativas=3,
        estrategia_erro='repetir',
        permite_voltar=False,
        permite_editar=True,
        ativo=True,
        variaveis_contexto={'tipo': 'nome_cliente'},
    )
    print(f"✅ Q1 criada: {q1.titulo[:50]}...")
    
    # 3. QUESTÃO 2: Escolha do canal (Site ou WhatsApp)
    q2 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=2,
        titulo="Show, {{nome}}! A contratação é rápida e segura. Quer fazer direto pelo site ou prefere continuar com nosso time pelo WhatsApp?",
        descricao="Permite o cliente escolher o canal de atendimento",
        tipo_questao='select',
        tipo_validacao='obrigatoria',
        opcoes_resposta=['site', 'whatsapp'],
        mensagem_erro_padrao="Por favor, escolha uma das opções: Site ou WhatsApp",
        max_tentativas=3,
        estrategia_erro='repetir',
        permite_voltar=True,
        permite_editar=True,
        ativo=True,
        template_questao="Show, {{nome}}! A contratação é rápida e segura.\n\nQuer fazer direto pelo site ou prefere continuar com nosso time pelo WhatsApp?",
        variaveis_contexto={'usa_nome': True},
        # Roteamento: Se escolher WhatsApp, redireciona para atendimento humano
        roteamento_respostas={
            'whatsapp': None,  # Será tratado como ação especial
            'site': None  # Continua no fluxo normal
        }
    )
    print(f"✅ Q2 criada: Canal de atendimento")
    
    # 4. QUESTÃO 3: Tipo de instalação (Casa ou Empresa)
    q3 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=3,
        titulo="A internet será para casa ou empresa?",
        descricao="Define o tipo de instalação",
        tipo_questao='select',
        tipo_validacao='obrigatoria',
        opcoes_resposta=['casa', 'empresa', 'residencial', 'comercial'],
        mensagem_erro_padrao="Por favor, escolha: Casa ou Empresa",
        max_tentativas=3,
        estrategia_erro='repetir',
        permite_voltar=True,
        permite_editar=True,
        ativo=True,
        variaveis_contexto={'tipo': 'tipo_instalacao'},
    )
    print(f"✅ Q3 criada: Tipo de instalação")
    
    # 5. QUESTÃO 4: Seleção de Plano (com opções dinâmicas)
    q4 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=4,
        titulo="Ótima notícia {{nome}}! Temos uma promoção exclusiva para este mês, com descontos especiais para pagamento via Pix ou App Mega!\n\nGostou ou quer ainda mais velocidade?",
        descricao="Apresenta os planos disponíveis com promoção",
        tipo_questao='planos_internet',
        tipo_validacao='obrigatoria',
        opcoes_dinamicas_fonte='planos_internet',
        mensagem_erro_padrao="Por favor, escolha um dos planos disponíveis.",
        max_tentativas=3,
        estrategia_erro='repetir',
        permite_voltar=True,
        permite_editar=True,
        ativo=True,
        template_questao="Ótima notícia {{nome}}! Temos uma promoção exclusiva para este mês, com descontos especiais para pagamento via Pix ou App Mega!\n\n*Escolha seu plano:*\n\n📶 *Plano 320MB* - R$ 89,90/mês\n📶 *Plano 620MB* - R$ 99,90/mês\n📶 *Plano 1GB Turbo* - R$ 129,90/mês\n\nGostou ou quer ainda mais velocidade?",
        variaveis_contexto={'mostrar_promocao': True, 'usa_nome': True},
        # Configuração manual das opções (já que temos IDs específicos)
        opcoes_resposta=[
            {'valor': '1647', 'texto': '320MB - R$ 89,90/mês', 'id_plano': 1647},
            {'valor': '1649', 'texto': '620MB - R$ 99,90/mês', 'id_plano': 1649},
            {'valor': '1648', 'texto': '1GB Turbo - R$ 129,90/mês', 'id_plano': 1648},
            {'valor': 'ver_mais', 'texto': '📋 Ver mais planos', 'tipo': 'acao_especial'}
        ],
        roteamento_respostas={
            'ver_mais': None  # Ação especial para mostrar mais planos
        }
    )
    print(f"✅ Q4 criada: Seleção de planos")
    
    # 6. QUESTÃO 5: Mensagem informativa (não requer resposta)
    q5 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=5,
        titulo="Agora vou te pedir algumas informações para verificar a disponibilidade dos nossos planos na sua região.",
        descricao="Mensagem informativa antes de solicitar o CEP",
        tipo_questao='texto',
        tipo_validacao='opcional',
        resposta_padrao='ok',
        mensagem_erro_padrao="",
        max_tentativas=1,
        estrategia_erro='pular',
        permite_voltar=True,
        permite_editar=False,
        ativo=True,
        variaveis_contexto={'tipo': 'mensagem_informativa'},
    )
    print(f"✅ Q5 criada: Mensagem informativa")
    
    # 7. QUESTÃO 6: Solicitar CEP (com validação e consulta automática)
    q6 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=6,
        titulo="Digite o seu CEP (Exemplo: XXXXX-XXX)",
        descricao="Coleta o CEP para consulta de viabilidade",
        tipo_questao='cep',
        tipo_validacao='obrigatoria',
        regex_validacao=r'^\d{5}-?\d{3}$',
        mensagem_erro_padrao="CEP inválido. Digite no formato: 12345-678 ou 12345678",
        instrucoes_resposta_correta="Digite apenas números ou no formato XXXXX-XXX",
        max_tentativas=5,
        estrategia_erro='repetir',
        permite_voltar=True,
        permite_editar=True,
        ativo=True,
        variaveis_contexto={
            'tipo': 'cep',
            'consultar_api': True,
            'api_endpoint': '/api/cep/{cep}/'
        },
        # Webhook para consultar CEP via N8N (opcional)
        webhook_n8n_pos_resposta='',  # Pode ser configurado depois
    )
    print(f"✅ Q6 criada: Coleta de CEP")
    
    # 8. QUESTÃO 7: Confirmação dos dados do endereço
    q7 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=7,
        titulo="Confirme seu endereço:\n\nCEP: {{ret_cep}}\nEstado: {{ret_estado}}\nCidade: {{ret_cidade}}\nBairro: {{ret_bairro}}\nRua: {{ret_rua}}\n\nOs dados estão corretos?",
        descricao="Confirmação dos dados retornados pela API de CEP",
        tipo_questao='boolean',
        tipo_validacao='obrigatoria',
        opcoes_resposta=['sim', 'não', 's', 'n', 'yes', 'no'],
        mensagem_erro_padrao="Por favor, responda Sim ou Não",
        max_tentativas=3,
        estrategia_erro='repetir',
        permite_voltar=True,
        permite_editar=True,
        ativo=True,
        template_questao="Confirme seu endereço:\n\n📍 *CEP:* {{ret_cep}}\n📍 *Estado:* {{ret_estado}}\n📍 *Cidade:* {{ret_cidade}}\n📍 *Bairro:* {{ret_bairro}}\n📍 *Rua:* {{ret_rua}}\n\nOs dados estão corretos?",
        variaveis_contexto={
            'usa_dados_cep': True,
            'campos_necessarios': ['ret_cep', 'ret_estado', 'ret_cidade', 'ret_bairro', 'ret_rua']
        },
        # Roteamento condicional
        roteamento_respostas={
            'sim': None,  # Continua para próxima questão
            's': None,
            'yes': None,
            'não': None,  # Volta para coleta manual de endereço
            'n': None,
            'no': None
        }
    )
    print(f"✅ Q7 criada: Confirmação de endereço")
    
    # Configurar roteamento da Q7 para Q6 se a resposta for "não"
    # (será tratado na lógica de negócio)
    
    # 9. QUESTÃO 8: Número do endereço
    q8 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=8,
        titulo="Certo! Agora digite apenas o número do endereço, sem o complemento:\n\n(Exemplo: N° 99)\n\nSe for uma residência sem número, envie s/n.",
        descricao="Coleta o número do endereço",
        tipo_questao='texto',
        tipo_validacao='obrigatoria',
        regex_validacao=r'^(s/n|S/N|sn|SN|\d+[A-Za-z]?)$',
        tamanho_maximo=20,
        mensagem_erro_padrao="Digite um número válido ou s/n para sem número",
        instrucoes_resposta_correta="Digite apenas o número (ex: 123) ou s/n se não houver número",
        max_tentativas=3,
        estrategia_erro='repetir',
        permite_voltar=True,
        permite_editar=True,
        ativo=True,
        variaveis_contexto={'tipo': 'numero_endereco'},
        questao_dependencia=q7,  # Só aparece se Q7 for confirmada
        valor_dependencia='sim'
    )
    print(f"✅ Q8 criada: Número do endereço")
    
    # 10. QUESTÃO 9: Ponto de referência
    q9 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=9,
        titulo="Informe um ponto de referência do endereço:\n\n(Exemplo: ao lado do mercado)",
        descricao="Coleta ponto de referência para facilitar instalação",
        tipo_questao='texto',
        tipo_validacao='obrigatoria',
        tamanho_minimo=5,
        tamanho_maximo=200,
        mensagem_erro_padrao="Por favor, informe um ponto de referência válido",
        instrucoes_resposta_correta="Descreva um local próximo para facilitar a localização",
        max_tentativas=3,
        estrategia_erro='pular',  # Se não conseguir, pula
        permite_voltar=True,
        permite_editar=True,
        ativo=True,
        variaveis_contexto={'tipo': 'ponto_referencia'},
    )
    print(f"✅ Q9 criada: Ponto de referência")
    
    # 11. QUESTÃO 10: Mensagem antes dos dados pessoais
    q10 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=10,
        titulo="Perfeito! Agora, para darmos sequência no seu cadastro, preciso confirmar algumas informações:",
        descricao="Mensagem informativa antes de coletar dados pessoais",
        tipo_questao='texto',
        tipo_validacao='opcional',
        resposta_padrao='ok',
        mensagem_erro_padrao="",
        max_tentativas=1,
        estrategia_erro='pular',
        permite_voltar=True,
        permite_editar=False,
        ativo=True,
        variaveis_contexto={'tipo': 'mensagem_informativa'},
    )
    print(f"✅ Q10 criada: Mensagem informativa")
    
    # 12. QUESTÃO 11: Nome completo (confirmação/correção)
    q11 = QuestaoFluxo.objects.create(
        fluxo=fluxo,
        indice=11,
        titulo="Qual é o seu nome completo, por gentileza?",
        descricao="Confirmação/correção do nome completo",
        tipo_questao='texto',
        tipo_validacao='obrigatoria',
        tamanho_minimo=5,
        tamanho_maximo=100,
        regex_validacao=r'^[A-Za-zÀ-ÿ\s]+$',
        mensagem_erro_padrao="Por favor, digite seu nome completo (apenas letras)",
        instrucoes_resposta_correta="Digite seu nome completo, incluindo sobrenomes",
        max_tentativas=3,
        estrategia_erro='repetir',
        permite_voltar=True,
        permite_editar=True,
        ativo=True,
        variaveis_contexto={'tipo': 'nome_completo_confirmacao'},
    )
    print(f"✅ Q11 criada: Nome completo")
    
    # Configurar questão padrão próxima para sequência normal
    q1.questao_padrao_proxima = q2
    q1.save()
    
    q2.questao_padrao_proxima = q3
    q2.save()
    
    q3.questao_padrao_proxima = q4
    q3.save()
    
    q4.questao_padrao_proxima = q5
    q4.save()
    
    q5.questao_padrao_proxima = q6
    q5.save()
    
    q6.questao_padrao_proxima = q7
    q6.save()
    
    q7.questao_padrao_proxima = q8
    q7.save()
    
    q8.questao_padrao_proxima = q9
    q8.save()
    
    q9.questao_padrao_proxima = q10
    q9.save()
    
    q10.questao_padrao_proxima = q11
    q10.save()
    
    print("\n✅ Sequência de questões configurada!")
    
    # Estatísticas finais
    total_questoes = fluxo.get_total_questoes()
    print(f"\n📊 RESUMO:")
    print(f"   - Fluxo: {fluxo.nome}")
    print(f"   - Status: {fluxo.get_status_display()}")
    print(f"   - Total de questões: {total_questoes}")
    print(f"   - Tipo: {fluxo.get_tipo_fluxo_display()}")
    print(f"   - Pode ser usado: {'✅ Sim' if fluxo.pode_ser_usado() else '❌ Não'}")
    
    print("\n" + "="*60)
    print("🎉 FLUXO DE VENDAS CRIADO COM SUCESSO!")
    print("="*60)
    
    # Listar todas as questões
    print("\n📋 QUESTÕES CADASTRADAS:\n")
    for questao in fluxo.get_questoes_ordenadas():
        print(f"   Q{questao.indice}: {questao.titulo[:60]}...")
        print(f"        Tipo: {questao.get_tipo_questao_display()}")
        print(f"        Validação: {questao.get_tipo_validacao_display()}")
        if questao.opcoes_resposta:
            print(f"        Opções: {len(questao.opcoes_resposta)} opções")
        if questao.questao_padrao_proxima:
            print(f"        Próxima: Q{questao.questao_padrao_proxima.indice}")
        print()
    
    return fluxo

def verificar_planos():
    """Verifica se os planos mencionados existem no sistema"""
    print("\n🔍 Verificando planos de internet...")
    
    planos_ids = [1647, 1648, 1649]
    planos_encontrados = []
    
    for plano_id in planos_ids:
        try:
            plano = PlanoInternet.objects.get(id_sistema_externo=plano_id, ativo=True)
            planos_encontrados.append(plano)
            print(f"   ✅ Plano {plano_id}: {plano.nome} - R$ {plano.valor_mensal}")
        except PlanoInternet.DoesNotExist:
            print(f"   ⚠️  Plano {plano_id}: NÃO ENCONTRADO (precisará ser cadastrado)")
    
    return planos_encontrados

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SCRIPT DE POPULAÇÃO DO FLUXO DE VENDAS")
    print("="*60 + "\n")
    
    # Verificar planos primeiro
    planos = verificar_planos()
    
    # Criar o fluxo
    fluxo = criar_fluxo_vendas()
    
    print("\n💡 PRÓXIMOS PASSOS:")
    print("   1. Acesse o admin Django: /admin/")
    print("   2. Navegue até: Fluxos de Atendimento")
    print("   3. Edite o fluxo criado para ajustes finos")
    print("   4. Configure webhooks N8N se necessário")
    print("   5. Teste o fluxo em ambiente de desenvolvimento")
    print("\n✅ Script executado com sucesso!\n")

