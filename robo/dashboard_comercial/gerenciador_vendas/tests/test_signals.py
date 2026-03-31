"""
Testes para os signals do modulo CRM.
Cobre: criar_oportunidade_automatica, verificar_conversao_historico.
"""
import pytest
from decimal import Decimal

from apps.comercial.leads.models import LeadProspecto, HistoricoContato
from apps.comercial.crm.models import (
    OportunidadeVenda,
    ConfiguracaoCRM,
    HistoricoPipelineEstagio,
)

from tests.factories import (
    LeadProspectoFactory,
    PipelineEstagioFactory,
)


@pytest.mark.django_db
class TestCriarOportunidadeAutomatica:
    """Testes para o signal criar_oportunidade_automatica (post_save LeadProspecto)."""

    def _setup_config(self, tenant):
        """Cria ConfiguracaoCRM com estagio inicial para o tenant."""
        estagio = PipelineEstagioFactory(
            tenant=tenant,
            nome='Novo',
            slug='novo-auto-test',
            tipo='novo',
            probabilidade_padrao=30,
        )
        config = ConfiguracaoCRM.objects.create(
            tenant=tenant,
            criar_oportunidade_automatico=True,
            score_minimo_auto_criacao=7,
            estagio_inicial_padrao=estagio,
        )
        return config, estagio

    def test_criar_oportunidade_automatica_quando_lead_qualificado(self, tenant_a, set_tenant):
        """Lead com score >= threshold deve gerar OportunidadeVenda automaticamente."""
        set_tenant(tenant_a)
        self._setup_config(tenant_a)

        lead = LeadProspecto.objects.create(
            tenant=tenant_a,
            nome_razaosocial='Lead Qualificado',
            telefone='+5589999100001',
            score_qualificacao=8,
        )

        assert OportunidadeVenda.all_tenants.filter(lead=lead).exists()
        op = OportunidadeVenda.all_tenants.get(lead=lead)
        assert op.origem_crm == 'automatico'
        assert op.estagio.tipo == 'novo'

    def test_criar_oportunidade_por_status_sucesso(self, tenant_a, set_tenant):
        """Lead com status_api='sucesso' tambem deve gerar oportunidade."""
        set_tenant(tenant_a)
        self._setup_config(tenant_a)

        lead = LeadProspecto.objects.create(
            tenant=tenant_a,
            nome_razaosocial='Lead Sucesso API',
            telefone='+5589999100002',
            status_api='sucesso',
        )

        assert OportunidadeVenda.all_tenants.filter(lead=lead).exists()

    def test_nao_cria_oportunidade_duplicada(self, tenant_a, set_tenant):
        """Salvar o lead novamente nao deve criar segunda oportunidade."""
        set_tenant(tenant_a)
        self._setup_config(tenant_a)

        lead = LeadProspecto.objects.create(
            tenant=tenant_a,
            nome_razaosocial='Lead Unico',
            telefone='+5589999100003',
            score_qualificacao=9,
        )
        assert OportunidadeVenda.all_tenants.filter(lead=lead).count() == 1

        # Salva novamente (update)
        lead.observacoes = 'atualizado'
        lead.save()
        assert OportunidadeVenda.all_tenants.filter(lead=lead).count() == 1

    def test_nao_cria_oportunidade_sem_config(self, tenant_a, set_tenant):
        """Sem ConfiguracaoCRM com criar_oportunidade_automatico, nao deve gerar oportunidade."""
        set_tenant(tenant_a)
        # Garantir que config existe mas com auto-criacao desabilitada
        ConfiguracaoCRM.all_tenants.update_or_create(
            pk=1,
            defaults={'criar_oportunidade_automatico': False, 'tenant': tenant_a},
        )

        lead = LeadProspecto.objects.create(
            tenant=tenant_a,
            nome_razaosocial='Lead Sem Config',
            telefone='+5589999100004',
            score_qualificacao=10,
        )
        assert not OportunidadeVenda.all_tenants.filter(lead=lead).exists()

    def test_nao_cria_oportunidade_com_score_baixo(self, tenant_a, set_tenant):
        """Lead com score abaixo do minimo e sem status sucesso nao gera oportunidade."""
        set_tenant(tenant_a)
        self._setup_config(tenant_a)

        lead = LeadProspecto.objects.create(
            tenant=tenant_a,
            nome_razaosocial='Lead Baixo Score',
            telefone='+5589999100005',
            score_qualificacao=3,
            status_api='pendente',
        )
        assert not OportunidadeVenda.all_tenants.filter(lead=lead).exists()


@pytest.mark.django_db
class TestVerificarConversaoHistorico:
    """Testes para o signal verificar_conversao_historico (post_save HistoricoContato)."""

    def _setup_pipeline(self, tenant):
        """Cria estagios inicial e ganho, config, e retorna (estagio_inicial, estagio_ganho)."""
        estagio_inicial = PipelineEstagioFactory(
            tenant=tenant,
            nome='Negociacao',
            slug='negociacao-sig-test',
            tipo='negociacao',
            is_final_ganho=False,
            is_final_perdido=False,
        )
        estagio_ganho = PipelineEstagioFactory(
            tenant=tenant,
            nome='Cliente Ativo',
            slug='cliente-ativo-sig-test',
            tipo='cliente',
            is_final_ganho=True,
            is_final_perdido=False,
        )
        ConfiguracaoCRM.objects.create(
            tenant=tenant,
            criar_oportunidade_automatico=False,
            estagio_inicial_padrao=estagio_inicial,
        )
        return estagio_inicial, estagio_ganho

    def test_conversao_move_oportunidade_para_ganho(self, tenant_a, set_tenant):
        """HistoricoContato com converteu_venda=True move a oportunidade para estagio de ganho."""
        set_tenant(tenant_a)
        estagio_inicial, estagio_ganho = self._setup_pipeline(tenant_a)

        lead = LeadProspectoFactory(tenant=tenant_a)
        lead._skip_crm_signal = True
        lead.save()

        op = OportunidadeVenda.objects.create(
            tenant=tenant_a,
            lead=lead,
            estagio=estagio_inicial,
            origem_crm='manual',
        )

        # Criar historico com converteu_venda=True dispara o signal
        HistoricoContato.objects.create(
            tenant=tenant_a,
            lead=lead,
            telefone=lead.telefone,
            status='venda_confirmada',
            converteu_venda=True,
            valor_venda=Decimal('99.90'),
        )

        op.refresh_from_db()
        assert op.estagio == estagio_ganho
        assert op.data_fechamento_real is not None
        assert op.valor_estimado == Decimal('99.90')

        # Deve existir historico de transicao
        historico = HistoricoPipelineEstagio.objects.filter(oportunidade=op)
        assert historico.exists()
        assert historico.first().estagio_anterior == estagio_inicial
        assert historico.first().estagio_novo == estagio_ganho

    def test_conversao_sem_oportunidade_nao_causa_erro(self, tenant_a, set_tenant):
        """Se nao existe OportunidadeVenda para o lead, o signal nao deve falhar."""
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        lead._skip_crm_signal = True
        lead.save()

        # Nenhuma oportunidade criada, nao deve levantar excecao
        HistoricoContato.objects.create(
            tenant=tenant_a,
            lead=lead,
            telefone=lead.telefone,
            status='venda_confirmada',
            converteu_venda=True,
        )

    def test_historico_sem_conversao_nao_move_estagio(self, tenant_a, set_tenant):
        """HistoricoContato com converteu_venda=False nao deve alterar a oportunidade."""
        set_tenant(tenant_a)
        estagio_inicial, _ = self._setup_pipeline(tenant_a)

        lead = LeadProspectoFactory(tenant=tenant_a)
        lead._skip_crm_signal = True
        lead.save()

        op = OportunidadeVenda.objects.create(
            tenant=tenant_a,
            lead=lead,
            estagio=estagio_inicial,
            origem_crm='manual',
        )

        HistoricoContato.objects.create(
            tenant=tenant_a,
            lead=lead,
            telefone=lead.telefone,
            status='fluxo_finalizado',
            converteu_venda=False,
        )

        op.refresh_from_db()
        assert op.estagio == estagio_inicial

    def test_oportunidade_ja_ganha_nao_muda(self, tenant_a, set_tenant):
        """Se a oportunidade ja esta no estagio de ganho, nao deve mudar novamente."""
        set_tenant(tenant_a)
        _, estagio_ganho = self._setup_pipeline(tenant_a)

        lead = LeadProspectoFactory(tenant=tenant_a)
        lead._skip_crm_signal = True
        lead.save()

        op = OportunidadeVenda.objects.create(
            tenant=tenant_a,
            lead=lead,
            estagio=estagio_ganho,
            origem_crm='manual',
        )

        HistoricoContato.objects.create(
            tenant=tenant_a,
            lead=lead,
            telefone=lead.telefone,
            status='venda_confirmada',
            converteu_venda=True,
        )

        # Nenhum historico de transicao deve ser criado
        assert not HistoricoPipelineEstagio.objects.filter(oportunidade=op).exists()
