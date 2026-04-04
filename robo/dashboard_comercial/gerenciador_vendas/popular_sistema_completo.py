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
from apps.cs.clube.models import MembroClube, NivelClube, RegraPontuacao, ExtratoPontuacao, PremioRoleta, ParticipanteRoleta
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
            tenant=tenant, gatilho=gatilho,
            defaults={'nome_exibicao': nome, 'pontos_saldo': saldo, 'pontos_xp': xp, 'ativo': True},
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

    # ── Distribuir data_cadastro dos membros nos ultimos 7 dias ────────
    for i, m in enumerate(MembroClube.all_tenants.filter(tenant=tenant)):
        dias_atras = random.randint(0, 6)
        horas = random.randint(8, 22)
        MembroClube.all_tenants.filter(pk=m.pk).update(
            data_cadastro=timezone.now() - timedelta(days=dias_atras, hours=horas)
        )
    print("  Datas de cadastro distribuidas nos ultimos 7 dias")

    # ── Regra telefone_verificado (para grafico de Validacoes) ─────────
    regra_tel, _ = RegraPontuacao.all_tenants.get_or_create(
        tenant=tenant, gatilho='telefone_verificado',
        defaults={'nome_exibicao': 'Telefone Verificado', 'pontos_saldo': 5, 'pontos_xp': 10, 'ativo': True},
    )
    # Criar extratos de validacao distribuidos nos ultimos 7 dias
    membros_validar = list(MembroClube.all_tenants.filter(tenant=tenant, validado=True))
    count_val = 0
    for m in membros_validar:
        dias_atras = random.randint(0, 6)
        ep = ExtratoPontuacao.objects.create(
            tenant=tenant, membro=m, regra=regra_tel,
            pontos_saldo_ganhos=5, pontos_xp_ganhos=10,
            descricao_extra='Telefone verificado via OTP',
        )
        ExtratoPontuacao.all_tenants.filter(pk=ep.pk).update(
            data_recebimento=timezone.now() - timedelta(days=dias_atras, hours=random.randint(8, 22))
        )
        count_val += 1
    print(f"  {count_val} validacoes de telefone criadas")

    # ── ParticipanteRoleta (Giros + Ganhadores) ───────────────────────
    nomes_premios = [p[0] for p in premios]
    count_giros = 0
    for m in membros_validar:
        n_giros = random.randint(1, 4)
        for _ in range(n_giros):
            ganhou = random.random() < 0.3  # 30% chance de ganhar
            premio_nome = random.choice(nomes_premios) if ganhou else 'Não foi dessa vez'
            pr = ParticipanteRoleta.objects.create(
                tenant=tenant, membro=m,
                nome=m.nome, cpf=m.cpf, email=m.email,
                telefone=m.telefone, cidade=m.cidade, estado=m.estado,
                premio=premio_nome,
                status='ganhou' if ganhou else 'reservado',
                saldo=m.saldo,
            )
            dias_atras = random.randint(0, 6)
            ParticipanteRoleta.all_tenants.filter(pk=pr.pk).update(
                data_criacao=timezone.now() - timedelta(days=dias_atras, hours=random.randint(8, 22))
            )
            count_giros += 1
    print(f"  {count_giros} giros da roleta ({ParticipanteRoleta.all_tenants.filter(tenant=tenant, status='ganhou').count()} ganhadores)")

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

    # ══════════════════════════════════════════════════════════════════════
    # ██  AURORA HQ — Popular TODOS os modulos  ██████████████████████████
    # ══════════════════════════════════════════════════════════════════════
    aurora_t = Tenant.objects.filter(slug='aurora-hq').first()
    if aurora_t:
        set_current_tenant(aurora_t)
        print("\n--- AURORA HQ ---")

        # Usuarios Aurora
        aurora_user = User.objects.filter(username='aurora').first()
        aurora_users = {}
        aurora_vendedores = [
            ('lucas_aurora', 'Lucas', 'Mendes', 'lucas@auroraisp.com.br'),
            ('camila_aurora', 'Camila', 'Reis', 'camila@auroraisp.com.br'),
            ('rafael_aurora', 'Rafael', 'Costa', 'rafael@auroraisp.com.br'),
        ]
        for uname, first, last, email in aurora_vendedores:
            u, created = User.objects.get_or_create(
                username=uname,
                defaults={'first_name': first, 'last_name': last, 'email': email, 'is_staff': True},
            )
            if created:
                u.set_password('aurora123')
                u.save()
            PerfilUsuario.objects.get_or_create(user=u, defaults={'tenant': aurora_t})
            aurora_users[uname] = u
        if aurora_user:
            aurora_users['aurora'] = aurora_user
        print(f"  {len(aurora_users)} usuarios Aurora")

        # Planos (produtos Aurora = planos SaaS que Aurora vende)
        planos_aurora_data = [
            ('Comercial Start', 0, 0, Decimal('297.00')),
            ('Comercial Pro', 0, 0, Decimal('497.00')),
            ('Marketing Start', 0, 0, Decimal('397.00')),
            ('Marketing Pro', 0, 0, Decimal('697.00')),
            ('CS Start', 0, 0, Decimal('197.00')),
        ]
        planos_a = {}
        for nome_pl, down, up, valor in planos_aurora_data:
            p, _ = PlanoInternet.all_tenants.get_or_create(
                tenant=aurora_t, nome=nome_pl,
                defaults={'velocidade_download': down, 'velocidade_upload': up, 'valor_mensal': valor, 'ativo': True},
            )
            planos_a[nome_pl] = p
        for dia in [5, 10, 15]:
            OpcaoVencimento.all_tenants.get_or_create(
                tenant=aurora_t, dia_vencimento=dia,
                defaults={'descricao': f'Dia {dia} de cada mes', 'ativo': True},
            )
        print("  5 planos Aurora + 3 vencimentos")

        # Campanhas Aurora
        campanhas_aurora = {
            'linkedin-isp': ('LinkedIn ISPs', 'linkedin-isp', 'outro', 'pago'),
            'abrint-evento': ('Evento ABRINT 2026', 'abrint-evento', 'outro', 'organico'),
            'google-aurora': ('Google Ads Aurora', 'google-aurora', 'google_ads', 'pago'),
            'indicacao-parceiro': ('Indicacao Parceiros', 'indicacao-parceiro', 'whatsapp', 'organico'),
        }
        camp_a = {}
        for codigo, (nome_c, cod, plat, tipo) in campanhas_aurora.items():
            c, _ = CampanhaTrafego.all_tenants.get_or_create(
                tenant=aurora_t, codigo=cod,
                defaults={'nome': nome_c, 'plataforma': plat, 'tipo_trafego': tipo, 'ativa': True, 'palavra_chave': cod},
            )
            camp_a[codigo] = c
        print(f"  {len(camp_a)} campanhas Aurora")

        # Pipeline B2B
        pipeline_a, _ = Pipeline.all_tenants.get_or_create(
            tenant=aurora_t, slug='vendas-b2b',
            defaults={'nome': 'Vendas B2B Provedores', 'tipo': 'vendas', 'padrao': True, 'cor_hex': '#8b5cf6'},
        )
        estagios_b2b = [
            (1, 'Lead Identificado', 'lead-identificado', 'novo', '#94a3b8', 5),
            (2, 'Contato Inicial', 'contato-inicial', 'qualificacao', '#3b82f6', 15),
            (3, 'Demo Agendada', 'demo-agendada', 'qualificacao', '#06b6d4', 30),
            (4, 'Trial Ativo', 'trial-ativo', 'negociacao', '#f59e0b', 50),
            (5, 'Proposta Enviada', 'proposta-enviada', 'negociacao', '#a855f7', 70),
            (6, 'Negociacao', 'negociacao', 'fechamento', '#ec4899', 85),
            (7, 'Cliente Ativo', 'cliente-ativo', 'cliente', '#22c55e', 100),
            (8, 'Perdido', 'perdido', 'perdido', '#ef4444', 0),
        ]
        est_a = {}
        for ordem, nome_e, slug_e, tipo_e, cor, prob in estagios_b2b:
            e, _ = PipelineEstagio.all_tenants.get_or_create(
                tenant=aurora_t, pipeline=pipeline_a, slug=slug_e,
                defaults={'nome': nome_e, 'tipo': tipo_e, 'ordem': ordem, 'cor_hex': cor,
                          'probabilidade_padrao': prob, 'is_final_ganho': (slug_e == 'cliente-ativo'),
                          'is_final_perdido': (slug_e == 'perdido')},
            )
            est_a[slug_e] = e

        ConfiguracaoCRM.all_tenants.get_or_create(
            tenant=aurora_t,
            defaults={'pipeline_padrao': pipeline_a, 'estagio_inicial_padrao': est_a['lead-identificado'],
                      'criar_oportunidade_automatico': True, 'score_minimo_auto_criacao': 6},
        )

        # Tags B2B
        tags_b2b = ['Enterprise', 'PME', 'HubSoft', 'ABRINT', 'Trial']
        tags_a = {}
        for t_nome in tags_b2b:
            tg, _ = TagCRM.all_tenants.get_or_create(tenant=aurora_t, nome=t_nome, defaults={'cor_hex': '#8b5cf6'})
            tags_a[t_nome] = tg

        # Equipe Aurora
        equipe_a, _ = EquipeVendas.all_tenants.get_or_create(
            tenant=aurora_t, nome='Equipe Comercial Aurora',
            defaults={'descricao': 'Time comercial B2B', 'lider': aurora_users.get('lucas_aurora'), 'cor_hex': '#8b5cf6'},
        )
        for uname, user in aurora_users.items():
            PerfilVendedor.all_tenants.get_or_create(
                user=user, defaults={'equipe': equipe_a, 'cargo': 'gerente' if uname == 'lucas_aurora' else 'vendedor', 'tenant': aurora_t},
            )
        print("  Pipeline B2B + 8 estagios + equipe + tags")

        # Leads B2B (provedores como leads)
        provedores_leads = [
            ('Megalink Internet', '12345678000101', '86999001001', 'contato@megalink.com.br', 'Teresina', 'PI'),
            ('NetFibra Telecom', '98765432000199', '11999002002', 'contato@netfibra.com.br', 'Sao Paulo', 'SP'),
            ('VeloxNet', '55566677000188', '21999003003', 'admin@veloxnet.com.br', 'Rio de Janeiro', 'RJ'),
            ('FibraMax ISP', '11122233000155', '31999004004', 'suporte@fibramax.com.br', 'Belo Horizonte', 'MG'),
            ('ConectaJa', '44455566000177', '41999005005', 'contato@conectaja.com.br', 'Curitiba', 'PR'),
            ('TurboNet', '77788899000166', '51999006006', 'admin@turbonet.com.br', 'Porto Alegre', 'RS'),
            ('SpeedLink Telecom', '33344455000144', '61999007007', 'contato@speedlink.com.br', 'Brasilia', 'DF'),
            ('RapiNet Fibra', '22233344000133', '71999008008', 'admin@rapinet.com.br', 'Salvador', 'BA'),
            ('TopNet ISP', '66677788000122', '81999009009', 'suporte@topnet.com.br', 'Recife', 'PE'),
            ('AlphaFibra', '99988877000111', '85999010010', 'admin@alphafibra.com.br', 'Fortaleza', 'CE'),
            ('DataLink Telecom', '11223344000166', '62999011011', 'contato@datalink.com.br', 'Goiania', 'GO'),
            ('FibraNet Sul', '55667788000155', '48999012012', 'admin@fibranetsul.com.br', 'Florianopolis', 'SC'),
            ('MaxiTelecom', '99887766000144', '92999013013', 'suporte@maxitelecom.com.br', 'Manaus', 'AM'),
            ('PrimeNet ISP', '33221100000133', '65999014014', 'contato@primenet.com.br', 'Cuiaba', 'MT'),
            ('NovaFibra', '77665544000122', '98999015015', 'admin@novafibra.com.br', 'Sao Luis', 'MA'),
            ('GigaNet Telecom', '11009988000111', '79999016016', 'contato@giganet.com.br', 'Aracaju', 'SE'),
            ('UltraLink ISP', '22334455000199', '84999017017', 'admin@ultralink.com.br', 'Natal', 'RN'),
            ('BrasilFibra', '44556677000188', '96999018018', 'suporte@brasilfibra.com.br', 'Macapa', 'AP'),
            ('CityNet Telecom', '66778899000177', '63999019019', 'contato@citynet.com.br', 'Teresina', 'PI'),
            ('ProFibra ISP', '88990011000166', '69999020020', 'admin@profibra.com.br', 'Porto Velho', 'RO'),
        ]
        estagio_dist_a = ['lead-identificado'] * 3 + ['contato-inicial'] * 4 + ['demo-agendada'] * 4 + \
                         ['trial-ativo'] * 3 + ['proposta-enviada'] * 2 + ['negociacao'] * 2 + \
                         ['cliente-ativo'] * 1 + ['perdido'] * 1

        leads_a = []
        for i, (nome_l, cnpj, tel, email, cidade, estado) in enumerate(provedores_leads):
            plano_escolhido = random.choice(list(planos_a.values()))
            score = random.randint(4, 10)
            dias_atras = random.randint(0, 45)

            lead = LeadProspecto(
                tenant=aurora_t, nome_razaosocial=nome_l,
                telefone=tel, email=email, cpf_cnpj=cnpj,
                valor=plano_escolhido.valor_mensal,
                origem=random.choice(['linkedin', 'site', 'indicacao', 'evento']),
                status_api=random.choice(['processado', 'sucesso', 'pendente']),
                score_qualificacao=score,
                cidade=cidade, estado=estado, cep='01000-000',
                bairro='Centro', campanha_origem=random.choice(list(camp_a.values())),
            )
            lead._skip_crm_signal = True
            lead.save()
            LeadProspecto.all_tenants.filter(pk=lead.pk).update(
                data_cadastro=timezone.now() - timedelta(days=dias_atras, hours=random.randint(0, 23))
            )
            leads_a.append(lead)
        print(f"  {len(leads_a)} leads B2B Aurora")

        # Prospectos Aurora
        for lead in leads_a[:10]:
            Prospecto.all_tenants.get_or_create(
                tenant=aurora_t, lead=lead,
                defaults={'status': 'processado'},
            )
        print("  10 prospectos Aurora")

        # Historicos de contato Aurora
        count_hist_a = 0
        for lead in leads_a:
            HistoricoContato.objects.create(
                tenant=aurora_t, lead=lead, telefone=lead.telefone,
                status='atendido', origem_contato='whatsapp',
                observacoes=f'Primeiro contato com {lead.nome_razaosocial}',
            )
            count_hist_a += 1
            if lead.score_qualificacao >= 6:
                HistoricoContato.objects.create(
                    tenant=aurora_t, lead=lead, telefone=lead.telefone,
                    status='convertido', origem_contato='whatsapp',
                    observacoes=f'Demo agendada com {lead.nome_razaosocial}',
                    converteu_venda=lead.score_qualificacao >= 8,
                    valor_venda=lead.valor if lead.score_qualificacao >= 8 else None,
                )
                count_hist_a += 1
        print(f"  {count_hist_a} historicos de contato Aurora")

        # Fluxo de Atendimento Aurora
        fluxo_a, _ = FluxoAtendimento.all_tenants.get_or_create(
            tenant=aurora_t, nome='Fluxo Qualificacao B2B',
            defaults={'tipo_fluxo': 'qualificacao', 'status': 'ativo', 'ativo': True},
        )
        questoes_b2b = [
            'Qual o nome do provedor?', 'Quantos clientes ativos?', 'Qual ERP utiliza?',
            'Qual modulo tem interesse?', 'Qual a principal dor hoje?', 'Quer agendar uma demo?',
        ]
        for idx, q in enumerate(questoes_b2b):
            QuestaoFluxo.all_tenants.get_or_create(
                tenant=aurora_t, fluxo=fluxo_a, indice=idx,
                defaults={'titulo': q, 'tipo_questao': 'texto', 'ativo': True},
            )
        total_q_a = QuestaoFluxo.all_tenants.filter(fluxo=fluxo_a).count()
        for lead in leads_a[:8]:
            AtendimentoFluxo.all_tenants.get_or_create(
                tenant=aurora_t, lead=lead, fluxo=fluxo_a,
                defaults={'status': 'finalizado' if lead.score_qualificacao >= 7 else 'em_andamento', 'total_questoes': total_q_a},
            )
        print("  1 fluxo B2B + 6 questoes + 8 atendimentos")

        # Oportunidades CRM Aurora
        for i, lead in enumerate(leads_a):
            est_slug = estagio_dist_a[i % len(estagio_dist_a)]
            vendedor = random.choice(list(aurora_users.values()))
            op = OportunidadeVenda.objects.create(
                tenant=aurora_t, pipeline=pipeline_a, lead=lead,
                estagio=est_a[est_slug], responsavel=vendedor,
                titulo=lead.nome_razaosocial, valor_estimado=lead.valor,
                probabilidade=est_a[est_slug].probabilidade_padrao,
                origem_crm='automatico' if lead.score_qualificacao >= 7 else 'manual',
            )
            if random.random() > 0.5:
                op.tags.add(random.choice(list(tags_a.values())))
        print(f"  {len(leads_a)} oportunidades CRM Aurora")

        # Tarefas CRM Aurora
        ops_a = OportunidadeVenda.all_tenants.filter(
            tenant=aurora_t, ativo=True
        ).exclude(estagio__tipo__in=['cliente', 'perdido'])[:10]
        tipos_tarefa_b2b = ['ligacao', 'email', 'followup', 'proposta', 'whatsapp']
        for op in ops_a:
            TarefaCRM.objects.create(
                tenant=aurora_t, oportunidade=op, lead=op.lead, responsavel=op.responsavel,
                tipo=random.choice(tipos_tarefa_b2b),
                titulo=f'Followup {op.lead.nome_razaosocial}',
                status=random.choice(['pendente', 'pendente', 'em_andamento']),
                prioridade=random.choice(['normal', 'alta', 'urgente']),
                data_vencimento=timezone.now() + timedelta(days=random.randint(-2, 7)),
            )
        print(f"  {ops_a.count()} tarefas CRM Aurora")

        # Notas internas Aurora
        notas_b2b = [
            'Provedor com 5.000 clientes, muito interessado no modulo Comercial.',
            'Usa HubSoft. Integração nativa é o diferencial decisivo.',
            'Pediu referencia de case. Enviar dados do case Megalink.',
            'Demo realizada, feedback muito positivo. Aguardando proposta.',
            'Trial ativo ha 15 dias, engajamento alto no CRM.',
        ]
        for op in OportunidadeVenda.all_tenants.filter(tenant=aurora_t)[:8]:
            NotaInterna.objects.create(
                tenant=aurora_t, oportunidade=op, lead=op.lead,
                autor=op.responsavel, conteudo=random.choice(notas_b2b),
                tipo=random.choice(['geral', 'reuniao', 'ligacao', 'importante']),
            )
        print("  8 notas internas Aurora")

        # Metas Aurora
        for u in aurora_users.values():
            MetaVendas.all_tenants.get_or_create(
                tenant=aurora_t, vendedor=u, periodo='mensal',
                data_inicio=timezone.now().replace(day=1).date(),
                defaults={
                    'tipo': 'individual',
                    'data_fim': (timezone.now().replace(day=1) + timedelta(days=32)).replace(day=1).date() - timedelta(days=1),
                    'meta_vendas_quantidade': random.randint(5, 15),
                    'meta_vendas_valor': Decimal(str(random.randint(10000, 30000))),
                    'meta_leads_qualificados': random.randint(20, 40),
                    'criado_por': aurora_user or u,
                },
            )
        print(f"  {len(aurora_users)} metas Aurora")

        # Deteccoes de campanha Aurora
        for lead in leads_a[:6]:
            campanha = random.choice(list(camp_a.values()))
            DeteccaoCampanha.objects.create(
                tenant=aurora_t, lead=lead, campanha=campanha,
                telefone=lead.telefone, mensagem_original=f'Vim pelo {campanha.nome}',
                mensagem_normalizada=f'vim pelo {campanha.nome.lower()}',
                trecho_detectado=campanha.codigo, metodo_deteccao='keyword',
                score_confianca=Decimal('0.90'), origem='whatsapp',
            )
        print("  6 deteccoes de campanha Aurora")

        # Notificacoes Aurora
        for codigo, nome_n, prio in tipos_notif:
            TipoNotificacao.all_tenants.get_or_create(
                tenant=aurora_t, codigo=codigo,
                defaults={'nome': nome_n, 'prioridade_padrao': prio, 'ativo': True},
            )
        for codigo, nome_n in canais:
            CanalNotificacao.all_tenants.get_or_create(
                tenant=aurora_t, codigo=codigo,
                defaults={'nome': nome_n, 'ativo': True},
            )
        tipo_lead_a = TipoNotificacao.all_tenants.filter(tenant=aurora_t, codigo='lead_novo').first()
        canal_sistema = CanalNotificacao.all_tenants.filter(tenant=aurora_t, codigo='sistema').first()
        if tipo_lead_a and canal_sistema:
            for lead in leads_a[:6]:
                Notificacao.objects.create(
                    tenant=aurora_t, tipo=tipo_lead_a, canal=canal_sistema,
                    titulo=f'Novo lead: {lead.nome_razaosocial}',
                    mensagem=f'Provedor identificado via {lead.origem}',
                    status='enviada',
                )
        print("  Notificacoes Aurora")

        # ── CS Aurora ──────────────────────────────────────────────────
        for nome_n, xp in niveis:
            NivelClube.all_tenants.get_or_create(
                tenant=aurora_t, nome=nome_n,
                defaults={'xp_necessario': xp},
            )
        for nome_r, gatilho, saldo, xp in regras:
            RegraPontuacao.all_tenants.get_or_create(
                gatilho=gatilho, tenant=aurora_t,
                defaults={'nome_exibicao': nome_r, 'pontos_saldo': saldo, 'pontos_xp': xp, 'ativo': True},
            )

        membros_aurora = []
        for lead in leads_a[:12]:
            m, _ = MembroClube.all_tenants.get_or_create(
                tenant=aurora_t, cpf=lead.cpf_cnpj.replace('.', '').replace('-', '')[:14],
                defaults={
                    'nome': lead.nome_razaosocial, 'email': lead.email,
                    'telefone': lead.telefone, 'cep': '01000-000',
                    'cidade': lead.cidade, 'estado': lead.estado,
                    'saldo': random.randint(50, 500),
                    'xp_total': random.randint(100, 3000),
                    'validado': True,
                },
            )
            membros_aurora.append(m)

        regra_pgto_a = RegraPontuacao.all_tenants.filter(tenant=aurora_t, gatilho='pagamento_em_dia').first()
        if regra_pgto_a:
            for m in membros_aurora[:8]:
                ExtratoPontuacao.all_tenants.get_or_create(
                    tenant=aurora_t, membro=m, regra=regra_pgto_a,
                    defaults={'pontos_saldo_ganhos': 10, 'pontos_xp_ganhos': 5, 'descricao_extra': 'Mensalidade em dia'},
                )

        for nome_pr, qtd in premios:
            PremioRoleta.all_tenants.get_or_create(
                tenant=aurora_t, nome=nome_pr,
                defaults={'quantidade': qtd, 'probabilidade': qtd},
            )

        cats_aurora = [
            ('Software', 'software', 'fa-laptop-code'),
            ('Infraestrutura', 'infraestrutura', 'fa-server'),
            ('Consultoria', 'consultoria', 'fa-handshake'),
            ('Treinamento', 'treinamento', 'fa-chalkboard-teacher'),
        ]
        categorias_a = {}
        for nome_c, slug_c, icone_c in cats_aurora:
            c, _ = CategoriaParceiro.all_tenants.get_or_create(
                tenant=aurora_t, slug=slug_c,
                defaults={'nome': nome_c, 'icone': icone_c},
            )
            categorias_a[slug_c] = c

        parceiros_aurora_data = [
            ('MikroTik Brasil', 'infraestrutura', '11988001001'),
            ('HubSoft ERP', 'software', '11988002002'),
            ('FibraConsult', 'consultoria', '11988003003'),
            ('ISP Academy', 'treinamento', '11988004004'),
            ('CloudCore Hosting', 'infraestrutura', '11988005005'),
        ]
        for nome_pa, cat_s, tel_pa in parceiros_aurora_data:
            p, _ = Parceiro.all_tenants.get_or_create(
                tenant=aurora_t, nome=nome_pa,
                defaults={'categoria': categorias_a[cat_s], 'contato_telefone': tel_pa, 'ativo': True},
            )
            CupomDesconto.all_tenants.get_or_create(
                tenant=aurora_t, parceiro=p, codigo=f'AURORA{nome_pa[:3].upper()}',
                defaults={
                    'titulo': f'10% OFF - {nome_pa}', 'descricao': 'Desconto exclusivo para clientes Aurora',
                    'tipo_desconto': 'percentual', 'valor_desconto': 10, 'modalidade': 'pontos', 'custo_pontos': 50,
                    'data_inicio': timezone.now().date(), 'data_fim': (timezone.now() + timedelta(days=90)).date(),
                    'ativo': True,
                },
            )

        for m in membros_aurora[:5]:
            Indicacao.all_tenants.get_or_create(
                tenant=aurora_t, membro_indicador=m,
                nome_indicado=f'Provedor indicado por {m.nome.split()[0]}',
                defaults={
                    'telefone_indicado': f'1199{random.randint(1000000, 9999999)}',
                    'status': random.choice(['pendente', 'contato_feito', 'convertido']),
                },
            )
        print(f"  Aurora CS: {len(membros_aurora)} membros, 5 parceiros, 5 indicacoes, 4 premios")

        # Distribuir datas de cadastro dos membros Aurora
        for m in MembroClube.all_tenants.filter(tenant=aurora_t):
            MembroClube.all_tenants.filter(pk=m.pk).update(
                data_cadastro=timezone.now() - timedelta(days=random.randint(0, 6), hours=random.randint(8, 22))
            )

        # Regra telefone_verificado Aurora
        regra_tel_a, _ = RegraPontuacao.all_tenants.get_or_create(
            tenant=aurora_t, gatilho='telefone_verificado',
            defaults={'nome_exibicao': 'Telefone Verificado', 'pontos_saldo': 5, 'pontos_xp': 10, 'ativo': True},
        )
        for m in membros_aurora[:8]:
            ep = ExtratoPontuacao.objects.create(
                tenant=aurora_t, membro=m, regra=regra_tel_a,
                pontos_saldo_ganhos=5, pontos_xp_ganhos=10,
                descricao_extra='Telefone verificado via OTP',
            )
            ExtratoPontuacao.all_tenants.filter(pk=ep.pk).update(
                data_recebimento=timezone.now() - timedelta(days=random.randint(0, 6), hours=random.randint(8, 22))
            )

        # Giros da roleta Aurora
        nomes_premios_a = [p[0] for p in premios]
        count_giros_a = 0
        for m in membros_aurora:
            for _ in range(random.randint(1, 3)):
                ganhou = random.random() < 0.3
                premio_nome = random.choice(nomes_premios_a) if ganhou else 'Não foi dessa vez'
                pr = ParticipanteRoleta.objects.create(
                    tenant=aurora_t, membro=m,
                    nome=m.nome, cpf=m.cpf, email=m.email,
                    telefone=m.telefone, cidade=m.cidade, estado=m.estado,
                    premio=premio_nome, status='ganhou' if ganhou else 'reservado', saldo=m.saldo,
                )
                ParticipanteRoleta.all_tenants.filter(pk=pr.pk).update(
                    data_criacao=timezone.now() - timedelta(days=random.randint(0, 6), hours=random.randint(8, 22))
                )
                count_giros_a += 1
        print(f"  Aurora: {count_giros_a} giros, validacoes e datas distribuidas")

        # Logs Aurora
        logs_aurora = [
            ('INFO', 'leads', 'Novo provedor identificado via LinkedIn'),
            ('INFO', 'crm', 'Demo agendada com NetFibra Telecom'),
            ('WARNING', 'suporte', 'SLA proximo de vencer no ticket #1'),
            ('INFO', 'cs', 'Clube: 3 novos membros esta semana'),
            ('ERROR', 'integracoes', 'Timeout ao sincronizar dados do provedor'),
            ('INFO', 'marketing', 'Campanha ABRINT gerou 4 leads'),
        ]
        for nivel, modulo, msg in logs_aurora:
            LogSistema.objects.create(tenant=aurora_t, nivel=nivel, modulo=modulo, mensagem=msg)
        print(f"  {len(logs_aurora)} logs Aurora")

        set_current_tenant(tenant)  # Volta para Megalink

    # ── Logs do Sistema (Megalink) ─────────────────────────────────────
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
    print(f"  {len(logs)} logs Megalink")

    # ── Resumo Geral ───────────────────────────────────────────────────
    print("\n=== RESUMO POR TENANT ===")
    for t in Tenant.objects.all():
        print(f"\n  [{t.nome}]")
        print(f"    Leads: {LeadProspecto.all_tenants.filter(tenant=t).count()}")
        print(f"    Prospectos: {Prospecto.all_tenants.filter(tenant=t).count()}")
        print(f"    Historicos: {HistoricoContato.all_tenants.filter(tenant=t).count()}")
        print(f"    Atendimentos: {AtendimentoFluxo.all_tenants.filter(tenant=t).count()}")
        print(f"    Oportunidades CRM: {OportunidadeVenda.all_tenants.filter(tenant=t).count()}")
        print(f"    Tarefas CRM: {TarefaCRM.all_tenants.filter(tenant=t).count()}")
        print(f"    Membros Clube: {MembroClube.all_tenants.filter(tenant=t).count()}")
        print(f"    Parceiros: {Parceiro.all_tenants.filter(tenant=t).count()}")
        print(f"    Tickets: {Ticket.all_tenants.filter(tenant=t).count()}")
        print(f"    Campanhas: {CampanhaTrafego.all_tenants.filter(tenant=t).count()}")
        print(f"    Notificacoes: {Notificacao.all_tenants.filter(tenant=t).count()}")
    print("\nSistema populado com sucesso!")


if __name__ == '__main__':
    run()
