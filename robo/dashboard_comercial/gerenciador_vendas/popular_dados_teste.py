#!/usr/bin/env python3
"""Popular banco com dados de teste para demonstração."""
import os
import sys
import random
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings_local')

import django
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from apps.sistema.models import Tenant, PerfilUsuario, ConfiguracaoEmpresa, LogSistema
from apps.sistema.middleware import set_current_tenant
from apps.comercial.leads.models import LeadProspecto, Prospecto, HistoricoContato
from apps.comercial.atendimento.models import FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo
from apps.comercial.cadastro.models import PlanoInternet, OpcaoVencimento
from apps.marketing.campanhas.models import CampanhaTrafego
from apps.notificacoes.models import TipoNotificacao, CanalNotificacao, Notificacao
from apps.cs.clube.models import MembroClube


def run():
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(
            nome="Megalink Internet", slug="megalink",
            modulo_comercial=True, modulo_marketing=True, modulo_cs=True,
            plano_comercial="pro", plano_marketing="start", plano_cs="start",
            ativo=True,
        )
        ConfiguracaoEmpresa.objects.create(
            tenant=tenant, nome_empresa="Megalink Internet", ativo=True,
        )
        print(f"  Tenant '{tenant.nome}' criado")

    # Vincular admin
    admin = User.objects.filter(is_superuser=True).first()
    if admin:
        PerfilUsuario.objects.get_or_create(user=admin, defaults={"tenant": tenant})
        admin.is_staff = True
        admin.save()

    # Garantir staff para todos os usuarios
    for u in User.objects.all():
        if not u.is_staff:
            u.is_staff = True
            u.save()

    set_current_tenant(tenant)

    # ── LEADS ──────────────────────────────────────────────────────
    leads_data = [
        ("Maria Silva", "86999110001", "maria@gmail.com", "123.456.789-01", Decimal("99.90"), "whatsapp", "processado", 8),
        ("Joao Santos", "86999110002", "joao@hotmail.com", "234.567.890-12", Decimal("149.90"), "whatsapp", "sucesso", 9),
        ("Ana Oliveira", "86999110003", "ana@outlook.com", "345.678.901-23", Decimal("99.90"), "site", "pendente", 5),
        ("Carlos Pereira", "86999110004", "carlos@empresa.com", "456.789.012-34", Decimal("199.90"), "whatsapp", "processado", 7),
        ("Fernanda Lima", "86999110005", "fernanda@provedor.com", "567.890.123-45", Decimal("129.90"), "indicacao", "sucesso", 10),
        ("Roberto Souza", "86999110006", "roberto@gmail.com", "678.901.234-56", Decimal("99.90"), "whatsapp", "erro", 3),
        ("Patricia Costa", "86999110007", "patricia@yahoo.com", "789.012.345-67", Decimal("149.90"), "whatsapp", "processado", 6),
        ("Lucas Mendes", "86999110008", "lucasm@gmail.com", "890.123.456-78", Decimal("79.90"), "facebook", "pendente", 4),
        ("Juliana Ferreira", "86999110009", "juliana@hotmail.com", "901.234.567-89", Decimal("199.90"), "whatsapp", "sucesso", 9),
        ("Pedro Almeida", "86999110010", "pedro@empresa.net", "012.345.678-90", Decimal("129.90"), "google", "processado", 7),
    ]

    leads = []
    for nome, tel, email, cpf, valor, origem, status, score in leads_data:
        lead = LeadProspecto(
            tenant=tenant,
            nome_razaosocial=nome,
            telefone=tel,
            email=email,
            cpf_cnpj=cpf,
            valor=valor,
            origem=origem,
            status_api=status,
            score_qualificacao=score,
            cidade="Teresina",
            estado="PI",
            cep="64000-000",
            bairro="Centro",
        )
        lead._skip_crm_signal = True
        lead.save()
        # Ajustar data para espalhar nos ultimos 7 dias
        LeadProspecto.all_tenants.filter(pk=lead.pk).update(
            data_cadastro=timezone.now() - timedelta(days=random.randint(0, 6), hours=random.randint(0, 23))
        )
        leads.append(lead)
    print(f"  {len(leads)} leads criados")

    # ── PROSPECTOS ──────────────────────────────────────────────────
    for lead in leads[:5]:
        Prospecto.objects.create(tenant=tenant, lead=lead, status="processado")
    print("  5 prospectos criados")

    # ── HISTORICO ──────────────────────────────────────────────────
    count_hist = 0
    for lead in leads:
        HistoricoContato.objects.create(
            tenant=tenant, lead=lead, telefone=lead.telefone,
            status="atendido", origem_contato="whatsapp",
            observacoes=f"Primeiro contato com {lead.nome_razaosocial}",
        )
        count_hist += 1
        if lead.score_qualificacao >= 7:
            HistoricoContato.objects.create(
                tenant=tenant, lead=lead, telefone=lead.telefone,
                status="convertido", origem_contato="whatsapp",
                observacoes=f"Documentos validados de {lead.nome_razaosocial}",
                converteu_venda=True, valor_venda=lead.valor,
            )
            count_hist += 1
    print(f"  {count_hist} historicos de contato criados")

    # ── FLUXO DE ATENDIMENTO ───────────────────────────────────────
    fluxo, _ = FluxoAtendimento.objects.get_or_create(
        tenant=tenant, nome="Fluxo de Vendas WhatsApp",
        defaults={"tipo_fluxo": "qualificacao", "status": "ativo", "ativo": True},
    )
    questoes = ["Qual seu nome completo?", "Qual seu CPF?", "Qual seu CEP?", "Qual plano de interesse?", "Tem alguma duvida?"]
    for i, q in enumerate(questoes):
        QuestaoFluxo.objects.get_or_create(
            tenant=tenant, fluxo=fluxo, indice=i,
            defaults={"titulo": q, "tipo_questao": "texto", "ativo": True},
        )
    total_q = QuestaoFluxo.all_tenants.filter(fluxo=fluxo).count()
    for lead in leads[:4]:
        AtendimentoFluxo.objects.create(
            tenant=tenant, lead=lead, fluxo=fluxo,
            status="finalizado" if lead.score_qualificacao >= 7 else "em_andamento",
            total_questoes=total_q,
        )
    print("  1 fluxo + 5 questoes + 4 atendimentos")

    # ── PLANOS DE INTERNET ─────────────────────────────────────────
    planos = [
        ("Internet 100MB", 100, 50, Decimal("79.90")),
        ("Internet 200MB", 200, 100, Decimal("99.90")),
        ("Internet 400MB", 400, 200, Decimal("129.90")),
        ("Internet 600MB", 600, 300, Decimal("149.90")),
        ("Internet 1GB", 1000, 500, Decimal("199.90")),
    ]
    for nome, down, up, valor in planos:
        PlanoInternet.objects.create(
            tenant=tenant, nome=nome, velocidade_download=down,
            velocidade_upload=up, valor_mensal=valor, ativo=True,
        )
    for dia in [5, 10, 15, 20, 25]:
        OpcaoVencimento.objects.create(
            tenant=tenant, dia_vencimento=dia,
            descricao=f"Dia {dia} de cada mes", ativo=True,
        )
    print("  5 planos + 5 vencimentos")

    # ── CAMPANHAS ──────────────────────────────────────────────────
    campanhas = [
        ("Google Ads Teresina", "google-ads-the", "google_ads", "pago"),
        ("Facebook Promo 200MB", "fb-promo-200", "facebook", "pago"),
        ("Instagram Stories", "ig-stories", "instagram", "pago"),
        ("Indicacao Amigos", "indicacao", "whatsapp", "organico"),
    ]
    for nome, codigo, plat, tipo in campanhas:
        CampanhaTrafego.objects.create(
            tenant=tenant, nome=nome, codigo=codigo,
            plataforma=plat, tipo_trafego=tipo, ativa=True,
            palavra_chave=codigo,
        )
    print("  4 campanhas")

    # ── NOTIFICACOES ───────────────────────────────────────────────
    tipos = [
        ("lead_novo", "Novo Lead", "normal"),
        ("venda_aprovada", "Venda Aprovada", "alta"),
        ("docs_pendentes", "Documentos Pendentes", "normal"),
        ("erro_integracao", "Erro de Integracao", "alta"),
    ]
    for codigo, nome, prio in tipos:
        TipoNotificacao.objects.get_or_create(
            tenant=tenant, codigo=codigo,
            defaults={"nome": nome, "prioridade_padrao": prio, "ativo": True},
        )
    canais = [("whatsapp", "WhatsApp"), ("email", "E-mail"), ("sistema", "Sistema")]
    for codigo, nome in canais:
        CanalNotificacao.objects.get_or_create(
            tenant=tenant, codigo=codigo,
            defaults={"nome": nome, "ativo": True},
        )
    tipo_lead = TipoNotificacao.objects.filter(codigo="lead_novo").first()
    canal_wpp = CanalNotificacao.objects.filter(codigo="whatsapp").first()
    if tipo_lead and canal_wpp:
        for lead in leads[:5]:
            Notificacao.objects.create(
                tenant=tenant, tipo=tipo_lead, canal=canal_wpp,
                titulo=f"Novo lead: {lead.nome_razaosocial}",
                mensagem=f"Lead {lead.nome_razaosocial} cadastrado via {lead.origem}",
                status="enviada",
            )
    print("  4 tipos + 3 canais + 5 notificacoes")

    # ── LOGS DO SISTEMA ────────────────────────────────────────────
    logs_data = [
        ("INFO", "leads", "Lead Maria Silva cadastrado com sucesso"),
        ("INFO", "integracoes", "Sincronizacao HubSoft concluida: 5 clientes"),
        ("WARNING", "atendimento", "Timeout na questao 3 do fluxo de vendas"),
        ("ERROR", "integracoes", "Falha na conexao com HubSoft: timeout 30s"),
        ("INFO", "crm", "Oportunidade criada para Joao Santos"),
        ("WARNING", "notificacoes", "Canal WhatsApp com atraso de 5min"),
        ("ERROR", "cadastro", "Erro ao gerar PDF do contrato"),
        ("CRITICAL", "sistema", "Banco de dados com latencia alta: 2.5s"),
        ("INFO", "marketing", "Campanha Google Ads detectou 3 leads hoje"),
        ("INFO", "dashboard", "Dashboard carregado em 1.2s"),
    ]
    for nivel, modulo, msg in logs_data:
        LogSistema.objects.create(tenant=tenant, nivel=nivel, modulo=modulo, mensagem=msg)
    print("  10 logs do sistema")

    # ── MEMBROS DO CLUBE ───────────────────────────────────────────
    membros = [
        ("Maria Silva", "12345678901", "maria@gmail.com", "86999110001", 150),
        ("Joao Santos", "23456789012", "joao@hotmail.com", "86999110002", 320),
        ("Fernanda Lima", "56789012345", "fernanda@provedor.com", "86999110005", 80),
    ]
    for nome, cpf, email, tel, saldo in membros:
        MembroClube.objects.create(
            tenant=tenant, nome=nome, cpf=cpf, email=email,
            telefone=tel, saldo=saldo, validado=True,
        )
    print("  3 membros do clube")

    print("\nDados de teste populados com sucesso!")


if __name__ == "__main__":
    run()
