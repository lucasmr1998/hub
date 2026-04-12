#!/usr/bin/env python3
"""
Script para popular o banco com dados iniciais de cadastro
"""

import os
import sys
import django
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings')
django.setup()

from apps.comercial.cadastro.models import ConfiguracaoCadastro, PlanoInternet, OpcaoVencimento

def criar_dados_iniciais():
    """Cria dados iniciais para o sistema de cadastro"""
    
    print("🚀 Criando dados iniciais para o sistema de cadastro...")
    print("=" * 60)
    
    # 1. Criar configuração de cadastro
    print("📋 Criando configuração de cadastro...")
    config, created = ConfiguracaoCadastro.objects.get_or_create(
        empresa='Megalink',
        defaults={
            'titulo_pagina': 'Cadastro de Cliente - Megalink',
            'subtitulo_pagina': 'Preencha seus dados para começar sua jornada com a melhor internet',
            'telefone_suporte': '(89) 2221-0068',
            'whatsapp_suporte': '558922210068',
            'email_suporte': 'contato@megalinkpiaui.com.br',
            'mostrar_selecao_plano': True,
            'cpf_obrigatorio': True,
            'email_obrigatorio': True,
            'telefone_obrigatorio': True,
            'endereco_obrigatorio': True,
            'validar_cep': True,
            'validar_cpf': True,
            'mostrar_progress_bar': True,
            'numero_etapas': 4,
            'mensagem_sucesso': 'Parabéns! Seu cadastro foi realizado com sucesso.',
            'instrucoes_pos_cadastro': 'Em breve nossa equipe entrará em contato para agendar a instalação.',
            'criar_lead_automatico': True,
            'origem_lead_padrao': 'site',
            'enviar_email_confirmacao': False,
            'enviar_whatsapp_confirmacao': False,
            'captcha_obrigatorio': False,
            'limite_tentativas_dia': 5,
            'ativo': True
        }
    )
    
    if created:
        print(f"✅ Configuração criada: {config.empresa}")
    else:
        print(f"ℹ️  Configuração já existe: {config.empresa}")
    
    # 2. Criar planos de internet
    print("\n📡 Criando planos de internet...")
    
    planos_data = [
        {
            'nome': 'Plano 320MB',
            'descricao': 'Internet de alta velocidade para uso doméstico e trabalho',
            'velocidade_download': 320,
            'velocidade_upload': 320,
            'valor_mensal': Decimal('89.90'),
            'id_sistema_externo': '1647',
            'wifi_6': False,
            'suporte_prioritario': False,
            'suporte_24h': True,
            'upload_simetrico': True,
            'ordem_exibicao': 1,
            'destaque': '',
            'ativo': True
        },
        {
            'nome': 'Plano 620MB',
            'descricao': 'Internet ultra-rápida para famílias e pequenas empresas',
            'velocidade_download': 620,
            'velocidade_upload': 620,
            'valor_mensal': Decimal('99.90'),
            'id_sistema_externo': '1649',
            'wifi_6': False,
            'suporte_prioritario': True,
            'suporte_24h': True,
            'upload_simetrico': True,
            'ordem_exibicao': 2,
            'destaque': 'popular',
            'ativo': True
        },
        {
            'nome': 'Plano 1GB',
            'descricao': 'Internet de última geração com Wi-Fi 6 e suporte VIP',
            'velocidade_download': 1000,
            'velocidade_upload': 1000,
            'valor_mensal': Decimal('129.90'),
            'id_sistema_externo': '1648',
            'wifi_6': True,
            'suporte_prioritario': True,
            'suporte_24h': True,
            'upload_simetrico': True,
            'ordem_exibicao': 3,
            'destaque': 'premium',
            'ativo': True
        },
        {
            'nome': 'Plano 250MB',
            'descricao': 'Internet econômica para uso básico',
            'velocidade_download': 250,
            'velocidade_upload': 250,
            'valor_mensal': Decimal('69.90'),
            'id_sistema_externo': '1646',
            'wifi_6': False,
            'suporte_prioritario': False,
            'suporte_24h': False,
            'upload_simetrico': True,
            'ordem_exibicao': 0,
            'destaque': 'economico',
            'ativo': True
        }
    ]
    
    for plano_data in planos_data:
        plano, created = PlanoInternet.objects.get_or_create(
            nome=plano_data['nome'],
            defaults=plano_data
        )
        
        if created:
            print(f"✅ Plano criado: {plano.nome} - R$ {plano.valor_mensal}")
        else:
            print(f"ℹ️  Plano já existe: {plano.nome}")
    
    # 3. Criar opções de vencimento
    print("\n📅 Criando opções de vencimento...")
    
    vencimentos_data = [
        {'dia_vencimento': 5, 'descricao': 'Dia 5', 'ordem_exibicao': 1, 'ativo': True},
        {'dia_vencimento': 10, 'descricao': 'Dia 10', 'ordem_exibicao': 2, 'ativo': True},
        {'dia_vencimento': 15, 'descricao': 'Dia 15', 'ordem_exibicao': 3, 'ativo': True},
        {'dia_vencimento': 20, 'descricao': 'Dia 20', 'ordem_exibicao': 4, 'ativo': True},
        {'dia_vencimento': 25, 'descricao': 'Dia 25', 'ordem_exibicao': 5, 'ativo': True},
        {'dia_vencimento': 30, 'descricao': 'Dia 30', 'ordem_exibicao': 6, 'ativo': True}
    ]
    
    for venc_data in vencimentos_data:
        venc, created = OpcaoVencimento.objects.get_or_create(
            dia_vencimento=venc_data['dia_vencimento'],
            defaults=venc_data
        )
        
        if created:
            print(f"✅ Vencimento criado: {venc.descricao}")
        else:
            print(f"ℹ️  Vencimento já existe: {venc.descricao}")
    
    # 4. Associar plano padrão à configuração
    if not config.plano_padrao:
        plano_padrao = PlanoInternet.objects.filter(destaque='popular').first()
        if plano_padrao:
            config.plano_padrao = plano_padrao
            config.save()
            print(f"\n🔗 Plano padrão associado: {plano_padrao.nome}")
    
    print("\n" + "=" * 60)
    print("✅ Dados iniciais criados com sucesso!")
    
    # 5. Resumo final
    print(f"\n📊 Resumo:")
    print(f"   Configurações: {ConfiguracaoCadastro.objects.count()}")
    print(f"   Planos: {PlanoInternet.objects.count()}")
    print(f"   Vencimentos: {OpcaoVencimento.objects.count()}")
    
    # 6. Listar planos ativos
    print(f"\n📡 Planos ativos:")
    planos_ativos = PlanoInternet.objects.filter(ativo=True).order_by('ordem_exibicao')
    for plano in planos_ativos:
        destaque = f" ({plano.destaque})" if plano.destaque else ""
        print(f"   • {plano.nome} - R$ {plano.valor_mensal}{destaque}")
    
    return True

if __name__ == '__main__':
    try:
        criar_dados_iniciais()
        print("\n🎉 Script executado com sucesso!")
    except Exception as e:
        print(f"\n❌ Erro durante execução: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
