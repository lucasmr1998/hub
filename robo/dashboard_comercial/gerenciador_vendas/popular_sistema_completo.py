#!/usr/bin/env python3
"""
Popular o sistema completo com dados realistas para demonstracao.
Popula: Leads, Prospectos, Historicos, Atendimentos, Clientes HubSoft,
        CRM (Pipeline, Oportunidades, Tarefas, Notas), Campanhas,
        Notificacoes, CS (Clube, Parceiros, Cupons, Indicacoes),
        Suporte (Tickets, Comentarios), Logs.

Uso: python popular_sistema_completo.py
"""
import os
import random
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings_local')

import django
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from apps.sistema.models import (
    Tenant, PerfilUsuario, ConfiguracaoEmpresa, LogSistema,
    ConfiguracaoSistema, StatusConfiguravel,
)
from apps.sistema.middleware import set_current_tenant
from apps.comercial.leads.models import LeadProspecto, Prospecto, HistoricoContato, ImagemLeadProspecto
from apps.comercial.atendimento.models import FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo, RespostaQuestao
from apps.comercial.cadastro.models import PlanoInternet, OpcaoVencimento, CadastroCliente
from apps.comercial.crm.models import (
    Pipeline, PipelineEstagio, OportunidadeVenda, TarefaCRM,
    NotaInterna, TagCRM, EquipeVendas, PerfilVendedor, MetaVendas,
    ConfiguracaoCRM,
)
from apps.marketing.campanhas.models import CampanhaTrafego, DeteccaoCampanha
from apps.notificacoes.models import TipoNotificacao, CanalNotificacao, Notificacao
from apps.integracoes.models import IntegracaoAPI, ClienteHubsoft, ServicoClienteHubsoft
from apps.cs.clube.models import MembroClube, NivelClube, RegraPontuacao, ExtratoPontuacao, PremioRoleta
from apps.cs.parceiros.models import CategoriaParceiro, Parceiro, CupomDesconto, ResgateCupom
from apps.cs.indicacoes.models import Indicacao
from apps.suporte.models import CategoriaTicket, SLAConfig, Ticket, ComentarioTicket


def run():
    print("\n=== POPULAR SISTEMA COMPLETO ===\n")

    # ── Tenant ──────────────────────────────────────────────────────────
    tenant, created = Tenant.objects.get_or_create(
        slug='megalink',
        defaults={
            'nome': 'Megalink Internet',
            'modulo_comercial': True, 'modulo_marketing': True, 'modulo_cs': True,
            'plano_comercial': 'pro', 'plano_marketing': 'start', 'plano_cs': 'start',
            'ativo': True,
        },
    )
    if created:
        print(f"  Tenant {tenant.nome} criado")
    ConfiguracaoEmpresa.all_tenants.get_or_create(
        tenant=tenant, defaults={'nome_empresa': 'Megalink Internet', 'ativo': True},
    )

    # Vincular superuser
    admin = User.objects.filter(is_superuser=True).first()
    if admin:
        PerfilUsuario.objects.get_or_create(user=admin, defaults={'tenant': tenant})

    set_current_tenant(tenant)

    # ── Usuarios ────────────────────────────────────────────────────────
    vendedores_data = [
        ('darlan', 'Darlan', 'Oliveira', 'darlan@megalink.com.br'),
        ('maria_v', 'Maria', 'Santos', 'maria@megalink.com.br'),
        ('joao_v', 'Joao', 'Lima', 'joao@megalink.com.br'),
    ]
    users = {}
    for username, first, last, email in vendedores_data:
        u, _ = User.objects.get_or_create(
            username=username,
            defaults={'first_name': first, 'last_name': last, 'email': email, 'is_staff': True},
        )
        if _:
            u.set_password('mega123')
            u.save()
        PerfilUsuario.objects.get_or_create(user=u, defaults={'tenant': tenant})
        users[username] = u
    print(f"  {len(users)} vendedores criados")

    # ── Planos de Internet ──────────────────────────────────────────────
    planos_data = [
        ('Fibra 100MB', 100, 50, Decimal('79.90')),
        ('Fibra 200MB', 200, 100, Decimal('99.90')),
        ('Fibra 400MB', 400, 200, Decimal('129.90')),
        ('Fibra 600MB', 600, 300, Decimal('149.90')),
        ('Fibra 1GB', 1000, 500, Decimal('199.90')),
    ]
    planos = {}
    for nome, down, up, valor in planos_data:
        p, _ = PlanoInternet.all_tenants.get_or_create(
            tenant=tenant, nome=nome,
            defaults={'velocidade_download': down, 'velocidade_upload': up, 'valor_mensal': valor, 'ativo': True},
        )
        planos[nome] = p

    for dia in [5, 10, 15, 20, 25]:
        OpcaoVencimento.all_tenants.get_or_create(
            tenant=tenant, dia_vencimento=dia,
            defaults={'descricao': f'Dia {dia} de cada mes', 'ativo': True},
        )
    print("  5 planos + 5 vencimentos")

    # ── Campanhas ───────────────────────────────────────────────────────
    campanhas_data = [
        ('Google Ads Teresina', 'google-the', 'google_ads', 'pago'),
        ('Facebook Promo 200MB', 'fb-200', 'facebook', 'pago'),
        ('Instagram Stories', 'ig-stories', 'instagram', 'pago'),
        ('Indicacao Amigos', 'indicacao', 'whatsapp', 'organico'),
        ('WhatsApp Organico', 'wpp-org', 'whatsapp', 'organico'),
    ]
    campanhas = {}
    for nome, codigo, plat, tipo in campanhas_data:
        c, _ = CampanhaTrafego.all_tenants.get_or_create(
            tenant=tenant, codigo=codigo,
            defaults={'nome': nome, 'plataforma': plat, 'tipo_trafego': tipo, 'ativa': True, 'palavra_chave': codigo},
        )
        campanhas[codigo] = c
    print(f"  {len(campanhas)} campanhas")

    # ── Pipeline CRM ────────────────────────────────────────────────────
    pipeline, _ = Pipeline.all_tenants.get_or_create(
        tenant=tenant, slug='vendas-b2c',
        defaults={'nome': 'Vendas B2C', 'tipo': 'vendas', 'padrao': True, 'cor_hex': '#3b82f6'},
    )
    estagios_crm = [
        (1, 'Novo Lead', 'novo-lead', 'novo', '#94a3b8', 10),
        (2, 'Qualificado', 'qualificado', 'qualificacao', '#3b82f6', 30),
        (3, 'Documentacao', 'documentacao', 'negociacao', '#f59e0b', 60),
        (4, 'Contrato', 'contrato', 'fechamento', '#8b5cf6', 85),
        (5, 'Ativado HubSoft', 'ativado', 'cliente', '#22c55e', 100),
        (6, 'Perdido', 'perdido', 'perdido', '#ef4444', 0),
    ]
    estagios = {}
    for ordem, nome, slug, tipo, cor, prob in estagios_crm:
        e, _ = PipelineEstagio.all_tenants.get_or_create(
            tenant=tenant, pipeline=pipeline, slug=slug,
            defaults={'nome': nome, 'tipo': tipo, 'ordem': ordem, 'cor_hex': cor,
                      'probabilidade_padrao': prob, 'is_final_ganho': (slug == 'ativado'),
                      'is_final_perdido': (slug == 'perdido')},
        )
        estagios[slug] = e

    ConfiguracaoCRM.all_tenants.get_or_create(
        tenant=tenant,
        defaults={'pipeline_padrao': pipeline, 'estagio_inicial_padrao': estagios['novo-lead'],
                  'criar_oportunidade_automatico': True, 'score_minimo_auto_criacao': 7},
    )

    # Tags
    tags_data = ['Comercial', 'Endereco', 'Documental', 'VIP', 'Retorno']
    tags = {}
    for t_nome in tags_data:
        tg, _ = TagCRM.all_tenants.get_or_create(tenant=tenant, nome=t_nome, defaults={'cor_hex': '#667eea'})
        tags[t_nome] = tg

    # Equipe
    equipe, _ = EquipeVendas.all_tenants.get_or_create(
        tenant=tenant, nome='Equipe Comercial',
        defaults={'descricao': 'Equipe principal de vendas', 'lider': users['darlan'], 'cor_hex': '#3b82f6'},
    )
    for username, user in users.items():
        PerfilVendedor.all_tenants.get_or_create(
            user=user, defaults={'equipe': equipe, 'cargo': 'gerente' if username == 'darlan' else 'vendedor', 'tenant': tenant},
        )

    print("  Pipeline B2C + 6 estagios + equipe + tags")

    # ── Leads ───────────────────────────────────────────────────────────
    nomes = [
        'Ana Paula Ferreira', 'Carlos Eduardo Souza', 'Fernanda Costa Lima',
        'Roberto Silva Neto', 'Juliana Mendes Rocha', 'Pedro Henrique Almeida',
        'Mariana Barbosa Santos', 'Lucas Gabriel Oliveira', 'Camila Rodrigues',
        'Thiago Nascimento', 'Patricia Gomes Duarte', 'Rafael Moreira',
        'Beatriz Carvalho', 'Anderson Pereira Pinto', 'Larissa Souza',
        'Felipe Martins', 'Isabela Ramos', 'Bruno Costa',
        'Amanda Vieira', 'Diego Fernandes', 'Priscila Araujo',
        'Gustavo Ribeiro', 'Natalia Freitas', 'Renato Dias',
        'Vanessa Lopes', 'Marcos Teixeira', 'Aline Nascimento',
        'Eduardo Barros', 'Sabrina Monteiro', 'Henrique Cardoso',
    ]
    bairros = ['Centro', 'Jockey', 'Fátima', 'Noivos', 'Ininga', 'Morros', 'Dirceu', 'Satélite', 'Piçarra', 'Mocambinho']
    origens = ['whatsapp', 'site', 'facebook', 'indicacao', 'google', 'instagram']
    status_list = ['processado', 'sucesso', 'pendente', 'erro', 'processado', 'sucesso', 'processado', 'sucesso']
    estagio_dist = ['novo-lead'] * 5 + ['qualificado'] * 8 + ['documentacao'] * 7 + ['contrato'] * 5 + ['ativado'] * 3 + ['perdido'] * 2

    leads = []
    for i, nome in enumerate(nomes):
        cpf = f'{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}'
        plano_escolhido = random.choice(list(planos.values()))
        campanha = random.choice(list(campanhas.values()))
        vendedor = random.choice(list(users.values()))
        score = random.randint(2, 10)
        status_api = random.choice(status_list)
        dias_atras = random.randint(0, 30)

        lead = LeadProspecto(
            tenant=tenant, nome_razaosocial=nome,
            telefone=f'8699{random.randint(9000000, 9999999)}',
            email=f'{nome.split()[0].lower()}{random.randint(1,99)}@gmail.com',
            cpf_cnpj=cpf, valor=plano_escolhido.valor_mensal,
            origem=random.choice(origens), status_api=status_api,
            score_qualificacao=score,
            cidade='Teresina', estado='PI', cep='64000-000',
            bairro=random.choice(bairros),
            campanha_origem=campanha,
        )
        lead._skip_crm_signal = True
        lead.save()
        LeadProspecto.all_tenants.filter(pk=lead.pk).update(
            data_cadastro=timezone.now() - timedelta(days=dias_atras, hours=random.randint(0, 23))
        )
        leads.append(lead)

    print(f"  {len(leads)} leads criados")

    # ── Prospectos ──────────────────────────────────────────────────────
    for lead in leads[:15]:
        Prospecto.all_tenants.get_or_create(
            tenant=tenant, lead=lead,
            defaults={'status': 'processado'},
        )
    print("  15 prospectos")

    # ── Historico de Contatos ───────────────────────────────────────────
    count_hist = 0
    for lead in leads:
        HistoricoContato.objects.create(
            tenant=tenant, lead=lead, telefone=lead.telefone,
            status='atendido', origem_contato='whatsapp',
            observacoes=f'Primeiro contato com {lead.nome_razaosocial}',
        )
        count_hist += 1
        if lead.score_qualificacao >= 6:
            HistoricoContato.objects.create(
                tenant=tenant, lead=lead, telefone=lead.telefone,
                status='convertido', origem_contato='whatsapp',
                observacoes=f'Documentos coletados de {lead.nome_razaosocial}',
                converteu_venda=lead.score_qualificacao >= 8,
                valor_venda=lead.valor if lead.score_qualificacao >= 8 else None,
            )
            count_hist += 1
    print(f"  {count_hist} historicos de contato")

    # ── Fluxo de Atendimento ───────────────────────────────────────────
    fluxo, _ = FluxoAtendimento.all_tenants.get_or_create(
        tenant=tenant, nome='Fluxo de Vendas WhatsApp',
        defaults={'tipo_fluxo': 'qualificacao', 'status': 'ativo', 'ativo': True},
    )
    questoes_txt = [
        'Qual seu nome completo?', 'Qual seu CPF?', 'Qual seu endereco com CEP?',
        'Qual plano de internet deseja?', 'Qual dia de vencimento prefere?',
        'Tem alguma duvida antes de prosseguir?',
    ]
    for idx, q in enumerate(questoes_txt):
        QuestaoFluxo.all_tenants.get_or_create(
            tenant=tenant, fluxo=fluxo, indice=idx,
            defaults={'titulo': q, 'tipo_questao': 'texto', 'ativo': True},
        )

    total_q = QuestaoFluxo.all_tenants.filter(fluxo=fluxo).count()
    for lead in leads[:12]:
        finalizado = lead.score_qualificacao >= 7
        AtendimentoFluxo.all_tenants.get_or_create(
            tenant=tenant, lead=lead, fluxo=fluxo,
            defaults={'status': 'finalizado' if finalizado else 'em_andamento', 'total_questoes': total_q},
        )
    print("  1 fluxo + 6 questoes + 12 atendimentos")

    # ── CRM Oportunidades ──────────────────────────────────────────────
    for i, lead in enumerate(leads):
        est_slug = estagio_dist[i % len(estagio_dist)]
        vendedor = random.choice(list(users.values()))
        op = OportunidadeVenda.objects.create(
            tenant=tenant, pipeline=pipeline, lead=lead,
            estagio=estagios[est_slug], responsavel=vendedor,
            titulo=lead.nome_razaosocial, valor_estimado=lead.valor,
            probabilidade=estagios[est_slug].probabilidade_padrao,
            origem_crm='automatico' if lead.score_qualificacao >= 7 else 'manual',
        )
        # Tags aleatorias
        if random.random() > 0.5:
            op.tags.add(random.choice(list(tags.values())))

    print(f"  {len(leads)} oportunidades CRM")

    # ── Tarefas CRM ────────────────────────────────────────────────────
    ops_abertas = OportunidadeVenda.all_tenants.filter(
        tenant=tenant, ativo=True
    ).exclude(estagio__tipo__in=['cliente', 'perdido'])[:15]
    tipos_tarefa = ['ligacao', 'whatsapp', 'email', 'followup', 'proposta', 'visita']
    for op in ops_abertas:
        TarefaCRM.objects.create(
            tenant=tenant, oportunidade=op, lead=op.lead, responsavel=op.responsavel,
            tipo=random.choice(tipos_tarefa),
            titulo=f'Contatar {op.lead.nome_razaosocial}',
            status=random.choice(['pendente', 'pendente', 'em_andamento']),
            prioridade=random.choice(['normal', 'normal', 'alta', 'urgente']),
            data_vencimento=timezone.now() + timedelta(days=random.randint(-2, 7)),
        )
    print(f"  {ops_abertas.count()} tarefas CRM")

    # ── Notas Internas ─────────────────────────────────────────────────
    notas_txt = [
        'Cliente muito interessado, pediu detalhes do plano.',
        'Mora em area de cobertura nova, verificar viabilidade.',
        'Indicacao do cliente Jose, dar prioridade.',
        'Documentos enviados, aguardando validacao.',
        'Contrato assinado digitalmente.',
    ]
    for op in OportunidadeVenda.all_tenants.filter(tenant=tenant)[:10]:
        NotaInterna.objects.create(
            tenant=tenant, oportunidade=op, lead=op.lead,
            autor=op.responsavel, conteudo=random.choice(notas_txt),
            tipo=random.choice(['geral', 'reuniao', 'ligacao', 'importante']),
        )
    print("  10 notas internas")

    # ── Metas de Vendas ────────────────────────────────────────────────
    for u in users.values():
        MetaVendas.all_tenants.get_or_create(
            tenant=tenant, vendedor=u, periodo='mensal',
            data_inicio=timezone.now().replace(day=1).date(),
            defaults={
                'tipo': 'individual',
                'data_fim': (timezone.now().replace(day=1) + timedelta(days=32)).replace(day=1).date() - timedelta(days=1),
                'meta_vendas_quantidade': random.randint(15, 30),
                'meta_vendas_valor': Decimal(str(random.randint(5000, 15000))),
                'meta_leads_qualificados': random.randint(30, 60),
                'criado_por': admin or u,
            },
        )
    print("  3 metas de vendas")

    # ── Deteccoes de Campanha ──────────────────────────────────────────
    for lead in leads[:10]:
        campanha = random.choice(list(campanhas.values()))
        DeteccaoCampanha.objects.create(
            tenant=tenant, lead=lead, campanha=campanha,
            telefone=lead.telefone, mensagem_original=f'Vim pelo {campanha.nome}',
            mensagem_normalizada=f'vim pelo {campanha.nome.lower()}',
            trecho_detectado=campanha.codigo, metodo_deteccao='keyword',
            score_confianca=Decimal('0.95'), origem='whatsapp',
        )
    print("  10 deteccoes de campanha")

    # ── Clientes HubSoft (simulados) ───────────────────────────────────
    import time
    base_id = int(time.time()) % 100000
    for i, lead in enumerate(leads[:8]):
        cliente, _ = ClienteHubsoft.objects.get_or_create(
            lead=lead,
            defaults={
                'id_cliente': base_id + i,
                'nome_razaosocial': lead.nome_razaosocial,
                'tipo_pessoa': 'pf',
                'cpf_cnpj': lead.cpf_cnpj,
                'telefone_primario': lead.telefone,
                'email_principal': lead.email,
                'ativo': True,
            },
        )
        plano = random.choice(list(planos.values()))
        ServicoClienteHubsoft.objects.get_or_create(
            cliente=cliente, id_cliente_servico=base_id + 10000 + i,
            defaults={
                'nome': plano.nome, 'valor': plano.valor_mensal,
                'velocidade_download': str(plano.velocidade_download),
                'velocidade_upload': str(plano.velocidade_upload),
                'status': 'Habilitado',
            },
        )
    print("  8 clientes HubSoft + servicos")

    # ── Notificacoes ───────────────────────────────────────────────────
    tipos_notif = [
        ('lead_novo', 'Novo Lead', 'normal'),
        ('venda_aprovada', 'Venda Aprovada', 'alta'),
        ('docs_pendentes', 'Documentos Pendentes', 'normal'),
        ('erro_integracao', 'Erro de Integracao', 'alta'),
    ]
    for codigo, nome, prio in tipos_notif:
        TipoNotificacao.all_tenants.get_or_create(
            tenant=tenant, codigo=codigo,
            defaults={'nome': nome, 'prioridade_padrao': prio, 'ativo': True},
        )
    canais = [('whatsapp', 'WhatsApp'), ('email', 'E-mail'), ('sistema', 'Sistema')]
    for codigo, nome in canais:
        CanalNotificacao.all_tenants.get_or_create(
            tenant=tenant, codigo=codigo,
            defaults={'nome': nome, 'ativo': True},
        )

    tipo_lead = TipoNotificacao.all_tenants.filter(tenant=tenant, codigo='lead_novo').first()
    canal_wpp = CanalNotificacao.all_tenants.filter(tenant=tenant, codigo='whatsapp').first()
    if tipo_lead and canal_wpp:
        for lead in leads[:8]:
            Notificacao.objects.create(
                tenant=tenant, tipo=tipo_lead, canal=canal_wpp,
                titulo=f'Novo lead: {lead.nome_razaosocial}',
                mensagem=f'Lead cadastrado via {lead.origem}',
                status='enviada',
            )
    print("  4 tipos + 3 canais + 8 notificacoes")

    # ── CS: Niveis do Clube ────────────────────────────────────────────
    niveis = [
        ('Bronze', 0),
        ('Prata', 500),
        ('Ouro', 1500),
        ('Diamante', 5000),
    ]
    for nome, xp in niveis:
        NivelClube.all_tenants.get_or_create(
            tenant=tenant, nome=nome,
            defaults={'xp_necessario': xp},
        )

    # Regras de Pontuacao
    regras = [
        ('Pagamento em dia', 'pagamento_em_dia', 10, 5),
        ('Fatura adiantada', 'fatura_adiantada', 20, 10),
        ('Indicacao aceita', 'indicacao_aceita', 50, 25),
        ('App instalado', 'app_instalado', 15, 8),
    ]
    for nome, gatilho, saldo, xp in regras:
        RegraPontuacao.all_tenants.get_or_create(
            gatilho=gatilho,
            defaults={'tenant': tenant, 'nome_exibicao': nome, 'pontos_saldo': saldo, 'pontos_xp': xp, 'ativo': True},
        )

    # Membros do Clube
    membros = []
    for lead in leads[:15]:
        m, created = MembroClube.all_tenants.get_or_create(
            tenant=tenant, cpf=lead.cpf_cnpj.replace('.', '').replace('-', '')[:11],
            defaults={
                'nome': lead.nome_razaosocial,
                'email': lead.email,
                'telefone': lead.telefone,
                'cep': '64000-000', 'cidade': 'Teresina', 'estado': 'PI',
                'saldo': random.randint(0, 300),
                'xp_total': random.randint(0, 2000),
                'validado': True,
            },
        )
        membros.append(m)

    # Extrato de pontuacao
    regra_pgto = RegraPontuacao.all_tenants.filter(tenant=tenant, gatilho='pagamento_em_dia').first()
    if regra_pgto:
        for m in membros[:10]:
            ExtratoPontuacao.objects.create(
                tenant=tenant, membro=m, regra=regra_pgto,
                pontos_saldo_ganhos=10, pontos_xp_ganhos=5,
                descricao_extra='Pagamento mensal em dia',
            )
    print(f"  4 niveis + 4 regras + {len(membros)} membros clube + extratos")

    # ── CS: Parceiros ──────────────────────────────────────────────────
    cats = [
        ('Alimentacao', 'alimentacao', 'fa-utensils'),
        ('Saude', 'saude', 'fa-heartbeat'),
        ('Educacao', 'educacao', 'fa-graduation-cap'),
        ('Lazer', 'lazer', 'fa-ticket-alt'),
    ]
    categorias = {}
    for nome, slug, icone in cats:
        c, _ = CategoriaParceiro.all_tenants.get_or_create(
            tenant=tenant, slug=slug,
            defaults={'nome': nome, 'icone': icone},
        )
        categorias[slug] = c

    parceiros_data = [
        ('Pizzaria do Chico', 'alimentacao', '86988001001'),
        ('Farmacia Saude+', 'saude', '86988002002'),
        ('Escola Futuro', 'educacao', '86988003003'),
        ('Cinema Teresina', 'lazer', '86988004004'),
        ('Academia FitMax', 'saude', '86988005005'),
    ]
    parceiros = []
    for nome, cat_slug, tel in parceiros_data:
        p, _ = Parceiro.all_tenants.get_or_create(
            tenant=tenant, nome=nome,
            defaults={'categoria': categorias[cat_slug], 'contato_telefone': tel, 'ativo': True},
        )
        parceiros.append(p)

    # Cupons
    for parceiro in parceiros:
        CupomDesconto.all_tenants.get_or_create(
            tenant=tenant, parceiro=parceiro, codigo=f'MEGA{parceiro.nome[:4].upper()}',
            defaults={
                'titulo': f'10% OFF na {parceiro.nome}',
                'descricao': f'Desconto exclusivo para membros Megalink',
                'tipo_desconto': 'percentual',
                'valor_desconto': 10,
                'modalidade': 'pontos',
                'custo_pontos': 50,
                'data_inicio': timezone.now().date(),
                'data_fim': (timezone.now() + timedelta(days=90)).date(),
                'ativo': True,
            },
        )
    print(f"  4 categorias + {len(parceiros)} parceiros + cupons")

    # ── CS: Indicacoes ─────────────────────────────────────────────────
    for m in membros[:5]:
        Indicacao.all_tenants.get_or_create(
            tenant=tenant, membro_indicador=m,
            nome_indicado=f'Amigo de {m.nome.split()[0]}',
            defaults={
                'telefone_indicado': f'8699{random.randint(1000000, 9999999)}',
                'status': random.choice(['pendente', 'contato_feito', 'convertido']),
            },
        )
    print("  5 indicacoes")

    # ── Premios da Roleta ──────────────────────────────────────────────
    premios = [
        ('Desconto 10% no plano', 5),
        ('Cupom R$20 parceiro', 10),
        ('Upgrade 1 mes gratis', 2),
        ('Camiseta Megalink', 3),
    ]
    for nome, qtd in premios:
        PremioRoleta.all_tenants.get_or_create(
            tenant=tenant, nome=nome,
            defaults={'quantidade': qtd, 'probabilidade': qtd},
        )
    print("  4 premios da roleta")

    # ── Suporte: Tickets ───────────────────────────────────────────────
    # Categorias e SLA ja criados pelo seed_aurora, criar para Megalink tambem
    cats_ticket = [
        ('Bug', 'bug', 'fa-bug'),
        ('Duvida', 'duvida', 'fa-question-circle'),
        ('Solicitacao', 'solicitacao', 'fa-hand-paper'),
    ]
    for nome, slug, icone in cats_ticket:
        CategoriaTicket.all_tenants.get_or_create(
            tenant=tenant, slug=slug,
            defaults={'nome': nome, 'icone': icone},
        )

    for tier, resp, resol in [('starter', 24, 72), ('start', 12, 48), ('pro', 4, 24)]:
        SLAConfig.all_tenants.get_or_create(
            tenant=tenant, plano_tier=tier,
            defaults={'tempo_primeira_resposta_horas': resp, 'tempo_resolucao_horas': resol},
        )

    # Tickets de exemplo
    aurora_tenant = Tenant.objects.filter(slug='aurora-hq').first()
    if aurora_tenant:
        aurora_user = User.objects.filter(username='aurora').first()
        cat_bug = CategoriaTicket.all_tenants.filter(tenant=aurora_tenant, slug='bug').first()
        cat_duvida = CategoriaTicket.all_tenants.filter(tenant=aurora_tenant, slug='duvida').first()

        tickets_data = [
            ('Erro ao sincronizar clientes HubSoft', 'A sincronizacao retorna timeout apos 30 segundos.', cat_bug, 'alta', 'em_andamento'),
            ('Como configurar fluxo de atendimento?', 'Preciso criar um fluxo novo para vendas por telefone.', cat_duvida, 'normal', 'aberto'),
            ('Dashboard nao carrega graficos', 'A pagina de dashboard fica em branco nos graficos.', cat_bug, 'normal', 'resolvido'),
        ]
        for titulo, desc, cat, prio, status in tickets_data:
            Ticket.all_tenants.get_or_create(
                tenant=aurora_tenant, titulo=titulo,
                defaults={
                    'descricao': desc, 'categoria': cat, 'prioridade': prio, 'status': status,
                    'solicitante': users.get('darlan', admin),
                    'atendente': aurora_user,
                    'tenant_cliente': tenant,
                },
            )

        # Comentarios nos tickets
        for ticket in Ticket.all_tenants.filter(tenant=aurora_tenant)[:2]:
            ComentarioTicket.objects.create(
                tenant=aurora_tenant, ticket=ticket, autor=aurora_user,
                mensagem='Estamos analisando o problema. Retorno em breve.',
                interno=False,
            )
            ComentarioTicket.objects.create(
                tenant=aurora_tenant, ticket=ticket, autor=aurora_user,
                mensagem='Verificar logs de integracao no monitoramento.',
                interno=True,
            )
    print("  3 tickets + comentarios")

    # ── Logs do Sistema ────────────────────────────────────────────────
    logs = [
        ('INFO', 'leads', 'Sincronizacao concluida: 30 leads processados'),
        ('INFO', 'integracoes', 'HubSoft: 8 clientes sincronizados'),
        ('WARNING', 'atendimento', 'Timeout na questao 3 do fluxo de vendas'),
        ('ERROR', 'integracoes', 'Falha na conexao com HubSoft: timeout 30s'),
        ('INFO', 'crm', '5 oportunidades movidas automaticamente'),
        ('WARNING', 'notificacoes', 'Canal WhatsApp com atraso de 5min'),
        ('ERROR', 'cadastro', 'Erro ao gerar PDF do contrato'),
        ('CRITICAL', 'sistema', 'Banco de dados com latencia alta: 2.5s'),
        ('INFO', 'marketing', 'Campanha Google Ads detectou 3 leads'),
        ('INFO', 'dashboard', 'Dashboard carregado em 1.2s'),
        ('INFO', 'cs', 'NPS enviado para 15 membros do clube'),
        ('WARNING', 'suporte', 'Ticket #1 com SLA proximo de vencer'),
    ]
    for nivel, modulo, msg in logs:
        LogSistema.objects.create(tenant=tenant, nivel=nivel, modulo=modulo, mensagem=msg)
    print(f"  {len(logs)} logs do sistema")

    # ── Resumo ─────────────────────────────────────────────────────────
    print("\n=== RESUMO ===")
    print(f"  Leads: {LeadProspecto.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Prospectos: {Prospecto.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Historicos: {HistoricoContato.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Atendimentos: {AtendimentoFluxo.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Oportunidades CRM: {OportunidadeVenda.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Tarefas CRM: {TarefaCRM.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Clientes HubSoft: {ClienteHubsoft.objects.count()}")
    print(f"  Membros Clube: {MembroClube.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Parceiros: {Parceiro.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Tickets: {Ticket.all_tenants.count()}")
    print(f"  Campanhas: {CampanhaTrafego.all_tenants.filter(tenant=tenant).count()}")
    print(f"  Notificacoes: {Notificacao.all_tenants.filter(tenant=tenant).count()}")
    print("\nSistema populado com sucesso!")


if __name__ == '__main__':
    run()
