"""
Testes para os models do modulo comercial.
Cobre: LeadProspecto, PlanoInternet, FluxoAtendimento, QuestaoFluxo,
       AtendimentoFluxo, OportunidadeVenda, PipelineEstagio.
"""
import pytest
from decimal import Decimal

from apps.comercial.leads.models import LeadProspecto
from apps.comercial.atendimento.models import FluxoAtendimento, AtendimentoFluxo
from apps.comercial.crm.models import OportunidadeVenda

from tests.factories import (
    LeadProspectoFactory,
    PlanoInternetFactory,
    FluxoAtendimentoFactory,
    QuestaoFluxoFactory,
    PipelineEstagioFactory,
)


# ============================================================================
# LeadProspecto
# ============================================================================

@pytest.mark.django_db
class TestLeadProspecto:

    def test_criar_lead_com_campos_obrigatorios(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        assert lead.pk is not None
        assert lead.nome_razaosocial is not None
        assert lead.telefone is not None

    def test_lead_auto_preenche_tenant(self, tenant_a, set_tenant):
        """Quando o tenant esta no thread-local, o TenantMixin o define automaticamente."""
        set_tenant(tenant_a)
        lead = LeadProspecto.objects.create(
            nome_razaosocial='Lead Sem Tenant Explicito',
            telefone='+5589999000001',
        )
        assert lead.tenant == tenant_a

    def test_lead_isolado_por_tenant(self, tenant_a, tenant_b, set_tenant):
        set_tenant(tenant_a)
        LeadProspectoFactory(tenant=tenant_a)

        set_tenant(tenant_b)
        LeadProspectoFactory(tenant=tenant_b)

        # Com tenant_a ativo, so deve ver 1 lead
        set_tenant(tenant_a)
        assert LeadProspecto.objects.count() == 1

        # Com tenant_b ativo, so deve ver 1 lead
        set_tenant(tenant_b)
        assert LeadProspecto.objects.count() == 1

        # Sem filtro de tenant, deve ver 2
        set_tenant(None)
        assert LeadProspecto.all_tenants.count() == 2

    def test_lead_score_qualificacao_default(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        assert lead.score_qualificacao is None

    def test_lead_str_retorna_nome(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(
            tenant=tenant_a,
            nome_razaosocial='Maria Silva',
            email='maria@teste.com',
        )
        assert 'Maria Silva' in str(lead)


# ============================================================================
# PlanoInternet
# ============================================================================

@pytest.mark.django_db
class TestPlanoInternet:

    def test_criar_plano_internet(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        plano = PlanoInternetFactory(
            tenant=tenant_a,
            nome='Turbo 500',
            velocidade_download=500,
            velocidade_upload=250,
            valor_mensal=Decimal('129.90'),
        )
        assert plano.pk is not None
        assert plano.ativo is True

    def test_plano_str_retorna_nome_velocidade(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        plano = PlanoInternetFactory(
            tenant=tenant_a,
            nome='Ultra',
            velocidade_download=600,
        )
        resultado = str(plano)
        assert 'Ultra' in resultado
        assert '600' in resultado


# ============================================================================
# FluxoAtendimento
# ============================================================================

@pytest.mark.django_db
class TestFluxoAtendimento:

    def test_criar_fluxo_atendimento(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        fluxo = FluxoAtendimentoFactory(tenant=tenant_a)
        assert fluxo.pk is not None
        assert fluxo.tipo_fluxo == 'qualificacao'

    def test_fluxo_ativo_default_true(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        fluxo = FluxoAtendimentoFactory(tenant=tenant_a)
        assert fluxo.ativo is True

    def test_fluxo_isolado_por_tenant(self, tenant_a, tenant_b, set_tenant):
        set_tenant(tenant_a)
        FluxoAtendimentoFactory(tenant=tenant_a)

        set_tenant(tenant_b)
        FluxoAtendimentoFactory(tenant=tenant_b)

        set_tenant(tenant_a)
        assert FluxoAtendimento.objects.count() == 1

        set_tenant(tenant_b)
        assert FluxoAtendimento.objects.count() == 1


# ============================================================================
# QuestaoFluxo
# ============================================================================

@pytest.mark.django_db
class TestQuestaoFluxo:

    def test_criar_questao_vinculada_ao_fluxo(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        fluxo = FluxoAtendimentoFactory(tenant=tenant_a)
        questao = QuestaoFluxoFactory(tenant=tenant_a, fluxo=fluxo, indice=1)
        assert questao.pk is not None
        assert questao.fluxo == fluxo

    def test_questao_ordenacao(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        fluxo = FluxoAtendimentoFactory(tenant=tenant_a)
        QuestaoFluxoFactory(tenant=tenant_a, fluxo=fluxo, indice=1, titulo='Primeira')
        QuestaoFluxoFactory(tenant=tenant_a, fluxo=fluxo, indice=2, titulo='Segunda')
        QuestaoFluxoFactory(tenant=tenant_a, fluxo=fluxo, indice=3, titulo='Terceira')

        ordenadas = list(fluxo.questoes.order_by('indice').values_list('indice', flat=True))
        assert ordenadas == [1, 2, 3]


# ============================================================================
# AtendimentoFluxo
# ============================================================================

@pytest.mark.django_db
class TestAtendimentoFluxo:

    def test_criar_atendimento_vinculado_a_lead_e_fluxo(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        fluxo = FluxoAtendimentoFactory(tenant=tenant_a)
        atendimento = AtendimentoFluxo.objects.create(
            tenant=tenant_a,
            lead=lead,
            fluxo=fluxo,
            total_questoes=5,
        )
        assert atendimento.pk is not None
        assert atendimento.lead == lead
        assert atendimento.fluxo == fluxo

    def test_atendimento_status_inicial(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        fluxo = FluxoAtendimentoFactory(tenant=tenant_a)
        atendimento = AtendimentoFluxo.objects.create(
            tenant=tenant_a,
            lead=lead,
            fluxo=fluxo,
            total_questoes=3,
        )
        assert atendimento.status == 'iniciado'
        assert atendimento.questao_atual == 1
        assert atendimento.questoes_respondidas == 0


# ============================================================================
# OportunidadeVenda
# ============================================================================

@pytest.mark.django_db
class TestOportunidadeVenda:

    def test_criar_oportunidade_vinculada_a_lead(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        lead._skip_crm_signal = True
        lead.save()
        estagio = PipelineEstagioFactory(tenant=tenant_a)
        op = OportunidadeVenda.objects.create(
            tenant=tenant_a,
            lead=lead,
            estagio=estagio,
            origem_crm='manual',
        )
        assert op.pk is not None
        assert op.lead == lead

    def test_oportunidade_auto_preenche_tenant(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        lead._skip_crm_signal = True
        lead.save()
        estagio = PipelineEstagioFactory(tenant=tenant_a)
        op = OportunidadeVenda.objects.create(
            lead=lead,
            estagio=estagio,
            origem_crm='manual',
        )
        assert op.tenant == tenant_a

    def test_oportunidade_isolada_por_tenant(self, tenant_a, tenant_b, set_tenant):
        set_tenant(tenant_a)
        lead_a = LeadProspectoFactory(tenant=tenant_a)
        lead_a._skip_crm_signal = True
        lead_a.save()
        estagio_a = PipelineEstagioFactory(tenant=tenant_a)
        OportunidadeVenda.objects.create(
            tenant=tenant_a, lead=lead_a, estagio=estagio_a, origem_crm='manual',
        )

        set_tenant(tenant_b)
        lead_b = LeadProspectoFactory(tenant=tenant_b)
        lead_b._skip_crm_signal = True
        lead_b.save()
        estagio_b = PipelineEstagioFactory(tenant=tenant_b)
        OportunidadeVenda.objects.create(
            tenant=tenant_b, lead=lead_b, estagio=estagio_b, origem_crm='manual',
        )

        set_tenant(tenant_a)
        assert OportunidadeVenda.objects.count() == 1

        set_tenant(tenant_b)
        assert OportunidadeVenda.objects.count() == 1


# ============================================================================
# PipelineEstagio
# ============================================================================

@pytest.mark.django_db
class TestPipelineEstagio:

    def test_criar_estagio(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        estagio = PipelineEstagioFactory(tenant=tenant_a, nome='Qualificacao')
        assert estagio.pk is not None
        assert str(estagio) == 'Qualificacao'

    def test_estagio_ganho_e_perdido(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        ganho = PipelineEstagioFactory(
            tenant=tenant_a, nome='Ganho', is_final_ganho=True, is_final_perdido=False,
        )
        perdido = PipelineEstagioFactory(
            tenant=tenant_a, nome='Perdido', is_final_ganho=False, is_final_perdido=True,
        )
        assert ganho.is_final_ganho is True
        assert ganho.is_final_perdido is False
        assert perdido.is_final_perdido is True
        assert perdido.is_final_ganho is False
