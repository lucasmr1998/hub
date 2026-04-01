#!/usr/bin/env python3
"""Configura o CRM da Aurora HQ com pipeline B2B e provedores de teste."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings_local')

import django
django.setup()

from apps.sistema.models import Tenant
from apps.sistema.middleware import set_current_tenant
from apps.comercial.crm.models import Pipeline, PipelineEstagio, OportunidadeVenda, ConfiguracaoCRM, TarefaCRM, NotaInterna
from apps.comercial.leads.models import LeadProspecto
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


def run():
    aurora = Tenant.objects.get(slug='aurora-hq')
    set_current_tenant(aurora)
    user = User.objects.get(username='aurora')

    # Limpar dados antigos
    Pipeline.all_tenants.filter(tenant=aurora).delete()
    LeadProspecto.all_tenants.filter(tenant=aurora).delete()

    # ── Pipeline conforme doc crm_parceiro.md ──────────────────────────

    pipeline = Pipeline.objects.create(
        tenant=aurora,
        nome="Vendas Provedores",
        slug="vendas-provedores",
        tipo="vendas",
        padrao=True,
        cor_hex="#818cf8",
        icone_fa="fa-building",
    )

    estagios_data = [
        (1, "Lead Identificado", "lead-identificado", "novo", "#94a3b8", 10, None),
        (2, "Em Contato", "em-contato", "qualificacao", "#3b82f6", 30, 48),
        (3, "Em Negociacao", "em-negociacao", "negociacao", "#f59e0b", 60, 72),
        (4, "Trial Ativo", "trial-ativo", "negociacao", "#8b5cf6", 80, 336),
        (5, "Finalizada", "finalizada", "fechamento", "#22c55e", 100, None),
    ]

    estagios = {}
    for ordem, nome, slug, tipo, cor, prob, sla in estagios_data:
        est = PipelineEstagio.objects.create(
            tenant=aurora, pipeline=pipeline,
            nome=nome, slug=slug, tipo=tipo, ordem=ordem,
            cor_hex=cor, probabilidade_padrao=prob, sla_horas=sla,
            is_final_ganho=(slug == "finalizada"),
        )
        estagios[slug] = est

    print(f"  Pipeline: {pipeline.nome} com {len(estagios)} estagios")

    # ── Config CRM ──────────────────────────────────────────────────────

    ConfiguracaoCRM.all_tenants.filter(tenant=aurora).delete()
    ConfiguracaoCRM.objects.create(
        tenant=aurora,
        pipeline_padrao=pipeline,
        estagio_inicial_padrao=estagios["lead-identificado"],
        criar_oportunidade_automatico=False,
        sla_alerta_horas_padrao=48,
    )
    print("  ConfiguracaoCRM criada")

    # ── Provedores como leads B2B ───────────────────────────────────────

    provedores = [
        ("Megalink Telecom", "86999001001", "darlan@megalink.com.br", "40.328.771/0001-27",
         "Megalink Telecom", "Teresina", "PI", "indicacao", 10, "trial-ativo",
         Decimal("1497.00"), "Primeiro cliente. 30k clientes. Usa HubSoft. Qualificacao A."),
        ("NetPiaui Fibra", "86999002002", "jose@netpiaui.com", "12.345.678/0001-90",
         "NetPiaui Fibra LTDA", "Parnaiba", "PI", "whatsapp", 7, "em-contato",
         Decimal("497.00"), "5k clientes. Usa HubSoft. Demo agendada."),
        ("ConectaNet", "99999003003", "marcos@conectanet.com.br", "23.456.789/0001-01",
         "ConectaNet Servicos", "Imperatriz", "MA", "whatsapp", 5, "lead-identificado",
         Decimal("297.00"), "2k clientes. Usa Voalle. Qualificacao B."),
        ("TurboLink ISP", "63999004004", "ana@turbolink.net", "34.567.890/0001-12",
         "TurboLink Telecomunicacoes", "Palmas", "TO", "indicacao", 8, "em-negociacao",
         Decimal("897.00"), "10k clientes. Usa HubSoft. Proposta enviada. Qualificacao A."),
        ("FibraMax Internet", "98999005005", "carlos@fibramax.com.br", "45.678.901/0001-23",
         "FibraMax Internet EIRELI", "Sao Luis", "MA", "whatsapp", 6, "em-contato",
         Decimal("497.00"), "8k clientes. Usa SGP. Qualificacao B."),
        ("RapidNet Telecom", "86999006006", "pedro@rapidnet.pi", "56.789.012/0001-34",
         "RapidNet Telecom SA", "Floriano", "PI", "indicacao", 4, "lead-identificado",
         Decimal("297.00"), "1.5k clientes. Sem ERP definido."),
        ("NordesteNet", "85999007007", "lucia@nordestenet.com", "67.890.123/0001-45",
         "NordesteNet Comunicacoes", "Fortaleza", "CE", "whatsapp", 9, "em-negociacao",
         Decimal("1497.00"), "25k clientes. Usa HubSoft. Follow-up D+5. Qualificacao A."),
        ("VelocidadeNet", "89999008008", "raimundo@velocidadenet.com.br", "78.901.234/0001-56",
         "VelocidadeNet LTDA", "Picos", "PI", "indicacao", 3, "lead-identificado",
         Decimal("297.00"), "800 clientes. Usa planilha. Qualificacao B."),
    ]

    for nome, tel, email, cnpj, empresa, cidade, estado, origem, score, est_slug, valor, obs in provedores:
        lead = LeadProspecto(
            tenant=aurora, nome_razaosocial=nome, telefone=tel, email=email,
            cpf_cnpj=cnpj, empresa=empresa, cidade=cidade, estado=estado,
            origem=origem, score_qualificacao=score, valor=valor, observacoes=obs,
        )
        lead._skip_crm_signal = True
        lead.save()

        OportunidadeVenda.objects.create(
            tenant=aurora, pipeline=pipeline, lead=lead,
            estagio=estagios[est_slug], responsavel=user,
            titulo=nome, valor_estimado=valor,
            probabilidade=estagios[est_slug].probabilidade_padrao,
            origem_crm="manual",
        )

    print(f"  {len(provedores)} provedores criados")

    # ── Tarefas ─────────────────────────────────────────────────────────

    for op in OportunidadeVenda.all_tenants.filter(tenant=aurora, estagio=estagios["em-contato"]):
        TarefaCRM.objects.create(
            tenant=aurora, oportunidade=op, lead=op.lead, responsavel=user,
            tipo="ligacao", titulo=f"Agendar demo com {op.lead.nome_razaosocial}",
            status="pendente", prioridade="alta",
            data_vencimento=timezone.now() + timedelta(days=3),
        )

    for op in OportunidadeVenda.all_tenants.filter(tenant=aurora, estagio=estagios["em-negociacao"]):
        TarefaCRM.objects.create(
            tenant=aurora, oportunidade=op, lead=op.lead, responsavel=user,
            tipo="followup", titulo=f"Follow-up proposta {op.lead.nome_razaosocial}",
            status="pendente", prioridade="normal",
            data_vencimento=timezone.now() + timedelta(days=2),
        )

    for op in OportunidadeVenda.all_tenants.filter(tenant=aurora, estagio=estagios["trial-ativo"]):
        TarefaCRM.objects.create(
            tenant=aurora, oportunidade=op, lead=op.lead, responsavel=user,
            tipo="suporte", titulo=f"Acompanhamento trial {op.lead.nome_razaosocial}",
            status="em_andamento", prioridade="alta",
            data_vencimento=timezone.now() + timedelta(days=7),
        )
    print("  Tarefas criadas")

    # ── Notas ───────────────────────────────────────────────────────────

    megalink = OportunidadeVenda.all_tenants.filter(tenant=aurora, titulo="Megalink Telecom").first()
    if megalink:
        NotaInterna.objects.create(
            tenant=aurora, oportunidade=megalink, lead=megalink.lead, autor=user,
            conteudo="Trial ativado em 30/03. 400 vendas/mes. Case principal da Aurora.",
            tipo="importante",
        )

    nordeste = OportunidadeVenda.all_tenants.filter(tenant=aurora, titulo="NordesteNet").first()
    if nordeste:
        NotaInterna.objects.create(
            tenant=aurora, oportunidade=nordeste, lead=nordeste.lead, autor=user,
            conteudo="Provedor grande (25k clientes). Decisor animado com a demo. Pediu proposta com desconto por volume.",
            tipo="reuniao",
        )
    print("  Notas criadas")
    print("\nCRM Aurora HQ configurado!")


if __name__ == "__main__":
    run()
