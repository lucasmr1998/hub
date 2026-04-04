"""
Testes de models de atendimento para aumentar cobertura.
"""
import pytest
from django.utils import timezone

from apps.sistema.middleware import set_current_tenant
from apps.comercial.atendimento.models import (
    FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo, RespostaQuestao, TentativaResposta,
)
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    FluxoAtendimentoFactory, QuestaoFluxoFactory, LeadProspectoFactory,
)


@pytest.fixture
def atend_setup(db):
    tenant = TenantFactory()
    set_current_tenant(tenant)
    ConfigEmpresaFactory(tenant=tenant)
    fluxo = FluxoAtendimentoFactory(tenant=tenant, nome='Fluxo Teste')
    q1 = QuestaoFluxoFactory(tenant=tenant, fluxo=fluxo, titulo='Nome?', tipo_questao='texto')
    q2 = QuestaoFluxoFactory(tenant=tenant, fluxo=fluxo, titulo='CPF?', tipo_questao='cpf')
    q3 = QuestaoFluxoFactory(tenant=tenant, fluxo=fluxo, titulo='CEP?', tipo_questao='cep')
    lead = LeadProspectoFactory.build(tenant=tenant)
    lead._skip_crm_signal = True
    lead._skip_automacao = True
    lead.save()
    return {'tenant': tenant, 'fluxo': fluxo, 'questoes': [q1, q2, q3], 'lead': lead}


class TestFluxoAtendimentoModel:
    def test_str(self, atend_setup):
        assert 'Fluxo Teste' in str(atend_setup['fluxo'])

    def test_get_total_questoes(self, atend_setup):
        assert atend_setup['fluxo'].get_total_questoes() == 3

    def test_fluxo_ativo(self, atend_setup):
        assert atend_setup['fluxo'].status == 'ativo'


class TestQuestaoFluxoModel:
    def test_str(self, atend_setup):
        q = atend_setup['questoes'][0]
        assert 'Nome?' in str(q)

    def test_tipo_questao(self, atend_setup):
        assert atend_setup['questoes'][1].tipo_questao == 'cpf'

    def test_ordering(self, atend_setup):
        questoes = QuestaoFluxo.objects.filter(fluxo=atend_setup['fluxo']).order_by('indice')
        indices = list(questoes.values_list('indice', flat=True))
        assert indices == sorted(indices)
        assert len(indices) == 3


class TestAtendimentoFluxoModel:
    def test_criar_atendimento(self, atend_setup):
        at = AtendimentoFluxo.objects.create(
            tenant=atend_setup['tenant'],
            lead=atend_setup['lead'],
            fluxo=atend_setup['fluxo'],
            status='em_andamento',
            total_questoes=3,
        )
        assert at.pk
        assert at.status == 'em_andamento'

    def test_finalizar_atendimento(self, atend_setup):
        at = AtendimentoFluxo.objects.create(
            tenant=atend_setup['tenant'],
            lead=atend_setup['lead'],
            fluxo=atend_setup['fluxo'],
            status='em_andamento',
            total_questoes=3,
        )
        at.status = 'finalizado'
        at.save()
        at.refresh_from_db()
        assert at.status == 'finalizado'

    def test_str(self, atend_setup):
        at = AtendimentoFluxo.objects.create(
            tenant=atend_setup['tenant'],
            lead=atend_setup['lead'],
            fluxo=atend_setup['fluxo'],
            status='em_andamento',
            total_questoes=3,
        )
        s = str(at)
        assert s  # Should not be empty


class TestRespostaQuestaoModel:
    def test_criar_resposta(self, atend_setup):
        at = AtendimentoFluxo.objects.create(
            tenant=atend_setup['tenant'],
            lead=atend_setup['lead'],
            fluxo=atend_setup['fluxo'],
            status='em_andamento',
            total_questoes=3,
        )
        resp = RespostaQuestao.objects.create(
            tenant=atend_setup['tenant'],
            atendimento=at,
            questao=atend_setup['questoes'][0],
            resposta='João Silva',
        )
        assert resp.pk
        assert resp.resposta == 'João Silva'

    def test_str(self, atend_setup):
        at = AtendimentoFluxo.objects.create(
            tenant=atend_setup['tenant'],
            lead=atend_setup['lead'],
            fluxo=atend_setup['fluxo'],
            status='em_andamento',
            total_questoes=3,
        )
        resp = RespostaQuestao.objects.create(
            tenant=atend_setup['tenant'],
            atendimento=at,
            questao=atend_setup['questoes'][0],
            resposta='Maria',
        )
        assert str(resp)


class TestTentativaRespostaModel:
    def test_criar_tentativa(self, atend_setup):
        at = AtendimentoFluxo.objects.create(
            tenant=atend_setup['tenant'],
            lead=atend_setup['lead'],
            fluxo=atend_setup['fluxo'],
            status='em_andamento',
            total_questoes=3,
        )
        tent = TentativaResposta.objects.create(
            tenant=atend_setup['tenant'],
            atendimento=at,
            questao=atend_setup['questoes'][0],
            tentativa_numero=1,
            resposta_original='Tentativa 1',
        )
        assert tent.pk
        assert tent.tentativa_numero == 1


class TestQuestaoTipos:
    """Testa diferentes tipos de questão."""

    def test_tipo_texto(self, atend_setup):
        q = QuestaoFluxoFactory(tenant=atend_setup['tenant'], fluxo=atend_setup['fluxo'], tipo_questao='texto', indice=10)
        assert q.tipo_questao == 'texto'

    def test_tipo_cpf(self, atend_setup):
        q = QuestaoFluxoFactory(tenant=atend_setup['tenant'], fluxo=atend_setup['fluxo'], tipo_questao='cpf', indice=11)
        assert q.tipo_questao == 'cpf'

    def test_tipo_cep(self, atend_setup):
        q = QuestaoFluxoFactory(tenant=atend_setup['tenant'], fluxo=atend_setup['fluxo'], tipo_questao='cep', indice=12)
        assert q.tipo_questao == 'cep'

    def test_tipo_email(self, atend_setup):
        q = QuestaoFluxoFactory(tenant=atend_setup['tenant'], fluxo=atend_setup['fluxo'], tipo_questao='email', indice=13)
        assert q.tipo_questao == 'email'

    def test_tipo_telefone(self, atend_setup):
        q = QuestaoFluxoFactory(tenant=atend_setup['tenant'], fluxo=atend_setup['fluxo'], tipo_questao='telefone', indice=14)
        assert q.tipo_questao == 'telefone'

    def test_tipo_opcao(self, atend_setup):
        q = QuestaoFluxoFactory(tenant=atend_setup['tenant'], fluxo=atend_setup['fluxo'], tipo_questao='opcao', indice=15)
        assert q.tipo_questao == 'opcao'

    def test_tipo_condicional(self, atend_setup):
        q = QuestaoFluxoFactory(tenant=atend_setup['tenant'], fluxo=atend_setup['fluxo'], tipo_questao='condicional', indice=16)
        assert q.tipo_questao == 'condicional'
