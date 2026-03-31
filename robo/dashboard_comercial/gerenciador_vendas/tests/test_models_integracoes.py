"""
Testes de modelo para o modulo Integracoes (IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft).
"""
import pytest
from datetime import timedelta
from django.utils import timezone

from apps.integracoes.models import IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft

from tests.factories import (
    IntegracaoAPIFactory,
    LogIntegracaoFactory,
    ClienteHubsoftFactory,
    ServicoClienteHubsoftFactory,
    LeadProspectoFactory,
    TenantFactory,
)


@pytest.mark.django_db
class TestIntegracaoAPI:

    def test_criar_integracao_api(self):
        integ = IntegracaoAPIFactory()
        assert integ.pk is not None
        assert integ.tipo == 'hubsoft'
        assert integ.ativa is True
        assert 'Ativa' in str(integ)

    def test_integracao_str_inativa(self):
        integ = IntegracaoAPIFactory(ativa=False)
        assert 'Inativa' in str(integ)

    def test_integracao_token_valido_sem_token(self):
        integ = IntegracaoAPIFactory()
        assert integ.token_valido is False

    def test_integracao_token_valido_expirado(self):
        integ = IntegracaoAPIFactory(
            access_token='abc123',
            token_expira_em=timezone.now() - timedelta(hours=1),
        )
        assert integ.token_valido is False

    def test_integracao_token_valido_ativo(self):
        integ = IntegracaoAPIFactory(
            access_token='abc123',
            token_expira_em=timezone.now() + timedelta(hours=1),
        )
        assert integ.token_valido is True


@pytest.mark.django_db
class TestLogIntegracao:

    def test_criar_log_integracao(self):
        log = LogIntegracaoFactory()
        assert log.pk is not None
        assert log.sucesso is True
        assert log.metodo == 'POST'

    def test_log_vinculado_a_integracao(self):
        integ = IntegracaoAPIFactory()
        log = LogIntegracaoFactory(integracao=integ)
        assert log.integracao == integ
        assert integ.logs.count() == 1

    def test_log_str_sucesso(self):
        log = LogIntegracaoFactory(sucesso=True)
        assert '[OK]' in str(log)

    def test_log_str_erro(self):
        log = LogIntegracaoFactory(sucesso=False)
        assert '[ERRO]' in str(log)

    def test_log_vinculado_a_lead(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        log = LogIntegracaoFactory(lead=lead)
        assert log.lead == lead


@pytest.mark.django_db
class TestClienteHubsoft:

    def test_criar_cliente_hubsoft(self):
        cliente = ClienteHubsoftFactory()
        assert cliente.pk is not None
        assert cliente.ativo is True

    def test_cliente_hubsoft_str(self):
        cliente = ClienteHubsoftFactory(nome_razaosocial='Maria Silva')
        assert 'Maria Silva' in str(cliente)
        assert 'Ativo' in str(cliente)

    def test_cliente_hubsoft_vinculado_a_lead(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        lead = LeadProspectoFactory(tenant=tenant_a)
        cliente = ClienteHubsoftFactory(lead=lead)
        assert cliente.lead == lead
        assert lead.clientes_hubsoft.count() == 1


@pytest.mark.django_db
class TestServicoClienteHubsoft:

    def test_criar_servico_cliente_hubsoft(self):
        servico = ServicoClienteHubsoftFactory()
        assert servico.pk is not None
        assert servico.nome is not None
        assert servico.cliente is not None

    def test_servico_vinculado_a_cliente(self):
        cliente = ClienteHubsoftFactory()
        servico = ServicoClienteHubsoftFactory(cliente=cliente)
        assert servico.cliente == cliente
        assert cliente.servicos.count() == 1

    def test_servico_str(self):
        servico = ServicoClienteHubsoftFactory(nome='Fibra 300MB', status='Ativo')
        assert 'Fibra 300MB' in str(servico)
        assert 'Ativo' in str(servico)
