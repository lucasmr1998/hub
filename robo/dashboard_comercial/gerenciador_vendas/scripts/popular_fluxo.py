"""
Script para popular o fluxo de vendas
Executar: python manage.py shell
>>> exec(open('popular_fluxo.py').read())
"""

from apps.comercial.atendimento.models import FluxoAtendimento, QuestaoFluxo
from apps.comercial.cadastro.models import PlanoInternet
from django.utils import timezone

def criar_fluxo():
    print("🚀 Iniciando criação do Fluxo de Vendas...")
    
    # Criar fluxo
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
        fluxo.questoes.all().delete()
        print("🗑️  Questões antigas removidas")
    
    # Q1: Nome
    q1 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=1,
        titulo="Olá! Tudo bem? Para começarmos, qual o seu nome, por favor?",
        tipo_questao='texto', tipo_validacao='obrigatoria',
        tamanho_minimo=3, tamanho_maximo=100,
        regex_validacao=r'^[A-Za-zÀ-ÿ\s]+$',
        max_tentativas=3, estrategia_erro='repetir', ativo=True
    )
    print(f"✅ Q1 criada")
    
    # Q2: Canal
    q2 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=2,
        titulo="Show! A contratação é rápida e segura. Quer fazer direto pelo site ou prefere continuar com nosso time pelo WhatsApp?",
        tipo_questao='select', tipo_validacao='obrigatoria',
        opcoes_resposta=['site', 'whatsapp'],
        template_questao="Show, {{nome}}! A contratação é rápida e segura.\n\nQuer fazer direto pelo site ou prefere continuar com nosso time pelo WhatsApp?",
        max_tentativas=3, estrategia_erro='repetir', ativo=True
    )
    print(f"✅ Q2 criada")
    
    # Q3: Tipo instalação
    q3 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=3,
        titulo="A internet será para casa ou empresa?",
        tipo_questao='select', tipo_validacao='obrigatoria',
        opcoes_resposta=['casa', 'empresa'],
        max_tentativas=3, estrategia_erro='repetir', ativo=True
    )
    print(f"✅ Q3 criada")
    
    # Q4: Planos
    q4 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=4,
        titulo="Ótima notícia! Temos uma promoção exclusiva para este mês. Gostou ou quer ainda mais velocidade?",
        tipo_questao='planos_internet', tipo_validacao='obrigatoria',
        opcoes_dinamicas_fonte='planos_internet',
        template_questao="Ótima notícia {{nome}}! Temos uma promoção exclusiva para este mês, com descontos especiais para pagamento via Pix ou App Mega!\n\n*Escolha seu plano:*\n\n📶 *Plano 320MB* - R$ 89,90/mês\n📶 *Plano 620MB* - R$ 99,90/mês\n📶 *Plano 1GB Turbo* - R$ 129,90/mês\n\nGostou ou quer ainda mais velocidade?",
        opcoes_resposta=[
            {'valor': '1647', 'texto': '320MB - R$ 89,90/mês', 'id_plano': 1647},
            {'valor': '1649', 'texto': '620MB - R$ 99,90/mês', 'id_plano': 1649},
            {'valor': '1648', 'texto': '1GB Turbo - R$ 129,90/mês', 'id_plano': 1648},
            {'valor': 'ver_mais', 'texto': '📋 Ver mais planos', 'tipo': 'acao_especial'}
        ],
        max_tentativas=3, estrategia_erro='repetir', ativo=True
    )
    print(f"✅ Q4 criada")
    
    # Q5: Mensagem
    q5 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=5,
        titulo="Agora vou te pedir algumas informações para verificar a disponibilidade dos nossos planos na sua região.",
        tipo_questao='texto', tipo_validacao='opcional',
        resposta_padrao='ok',
        max_tentativas=1, estrategia_erro='pular', ativo=True
    )
    print(f"✅ Q5 criada")
    
    # Q6: CEP
    q6 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=6,
        titulo="Digite o seu CEP (Exemplo: XXXXX-XXX)",
        tipo_questao='cep', tipo_validacao='obrigatoria',
        regex_validacao=r'^\d{5}-?\d{3}$',
        mensagem_erro_padrao="CEP inválido. Digite no formato: 12345-678 ou 12345678",
        max_tentativas=5, estrategia_erro='repetir', ativo=True
    )
    print(f"✅ Q6 criada")
    
    # Q7: Confirmação endereço
    q7 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=7,
        titulo="Os dados estão corretos?",
        tipo_questao='boolean', tipo_validacao='obrigatoria',
        opcoes_resposta=['sim', 'não'],
        template_questao="Confirme seu endereço:\n\n📍 *CEP:* {{ret_cep}}\n📍 *Estado:* {{ret_estado}}\n📍 *Cidade:* {{ret_cidade}}\n📍 *Bairro:* {{ret_bairro}}\n📍 *Rua:* {{ret_rua}}\n\nOs dados estão corretos?",
        max_tentativas=3, estrategia_erro='repetir', ativo=True
    )
    print(f"✅ Q7 criada")
    
    # Q8: Número
    q8 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=8,
        titulo="Certo! Agora digite apenas o número do endereço, sem o complemento (ou s/n se não houver número):",
        tipo_questao='texto', tipo_validacao='obrigatoria',
        regex_validacao=r'^(s/n|S/N|sn|SN|\d+[A-Za-z]?)$',
        tamanho_maximo=20,
        max_tentativas=3, estrategia_erro='repetir', ativo=True
    )
    print(f"✅ Q8 criada")
    
    # Q9: Referência
    q9 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=9,
        titulo="Informe um ponto de referência do endereço (Exemplo: ao lado do mercado):",
        tipo_questao='texto', tipo_validacao='obrigatoria',
        tamanho_minimo=5, tamanho_maximo=200,
        max_tentativas=3, estrategia_erro='pular', ativo=True
    )
    print(f"✅ Q9 criada")
    
    # Q10: Mensagem
    q10 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=10,
        titulo="Perfeito! Agora, para darmos sequência no seu cadastro, preciso confirmar algumas informações:",
        tipo_questao='texto', tipo_validacao='opcional',
        resposta_padrao='ok',
        max_tentativas=1, estrategia_erro='pular', ativo=True
    )
    print(f"✅ Q10 criada")
    
    # Q11: Nome completo
    q11 = QuestaoFluxo.objects.create(
        fluxo=fluxo, indice=11,
        titulo="Qual é o seu nome completo, por gentileza?",
        tipo_questao='texto', tipo_validacao='obrigatoria',
        tamanho_minimo=5, tamanho_maximo=100,
        regex_validacao=r'^[A-Za-zÀ-ÿ\s]+$',
        max_tentativas=3, estrategia_erro='repetir', ativo=True
    )
    print(f"✅ Q11 criada")
    
    # Configurar sequência
    q1.questao_padrao_proxima = q2
    q2.questao_padrao_proxima = q3
    q3.questao_padrao_proxima = q4
    q4.questao_padrao_proxima = q5
    q5.questao_padrao_proxima = q6
    q6.questao_padrao_proxima = q7
    q7.questao_padrao_proxima = q8
    q8.questao_padrao_proxima = q9
    q9.questao_padrao_proxima = q10
    q10.questao_padrao_proxima = q11
    
    for q in [q1, q2, q3, q4, q5, q6, q7, q8, q9, q10]:
        q.save()
    
    print("\n✅ Sequência configurada!")
    print(f"\n📊 RESUMO:")
    print(f"   - Fluxo: {fluxo.nome}")
    print(f"   - Total de questões: {fluxo.get_total_questoes()}")
    print(f"   - Status: {fluxo.get_status_display()}")
    print(f"\n🎉 CONCLUÍDO!")
    
    return fluxo

# Executar
fluxo = criar_fluxo()

