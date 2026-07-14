"""
Regressao da acao `criar_tarefa` da engine legada de automacao de pipeline.

Contexto (14/07/2026): a acao importava `Tarefa`, nome que nunca existiu (a classe
e `TarefaCRM`). O ImportError era engolido pelo try/except de _executar_acoes_regra,
entao a regra registrava 'erro' num log e a tarefa nunca era criada, em silencio.

Impacto real: a Nuvyon tinha a regra "Viabilidade pendente revisao -> criar tarefa"
ativa, com 34 disparos e ZERO tarefas criadas.

Os testes chamam _acao_criar_tarefa DIRETO de proposito. Passar pelo executor da
regra nao serve de regressao: ele engole a excecao e o teste passaria mesmo quebrado.
"""
import pytest

from apps.sistema.middleware import set_current_tenant
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory, PipelineEstagioFactory, OportunidadeVendaFactory,
)


@pytest.fixture
def tenant_a(db):
    tenant = TenantFactory(slug='alpha', nome='Alpha', plano_comercial='pro', modulo_comercial=True)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)
    return tenant


@pytest.fixture
def vendedor(db, tenant_a):
    user = UserFactory(username='vendedora')
    PerfilFactory(user=user, tenant=tenant_a)
    return user


@pytest.fixture
def oportunidade_a(db, tenant_a, vendedor):
    estagio = PipelineEstagioFactory(
        tenant=tenant_a, nome='Novo', slug='novo', ordem=0, tipo='novo',
    )
    lead = LeadProspectoFactory(tenant=tenant_a)
    return OportunidadeVendaFactory(
        tenant=tenant_a, lead=lead, estagio=estagio, responsavel=vendedor,
    )


@pytest.mark.django_db
def test_acao_criar_tarefa_cria_tarefa_de_verdade(tenant_a, oportunidade_a):
    """O bug da Nuvyon: a acao dizia que rodou e nao criava nada."""
    from apps.comercial.crm.models import TarefaCRM
    from apps.comercial.crm.services.automacao_pipeline import _acao_criar_tarefa

    assert TarefaCRM.objects.filter(oportunidade=oportunidade_a).count() == 0

    ok = _acao_criar_tarefa(oportunidade_a, {
        'titulo': 'Revisar viabilidade',
        'descricao': 'Viabilidade pendente de revisao humana.',
        'prazo_horas': 4,
        'prioridade': 'alta',
        'tipo': 'followup',
    })

    assert ok is True
    tarefas = TarefaCRM.objects.filter(oportunidade=oportunidade_a)
    assert tarefas.count() == 1

    t = tarefas.first()
    assert t.titulo == 'Revisar viabilidade'
    assert t.prioridade == 'alta'
    assert t.tipo == 'followup'
    assert t.status == 'pendente'
    assert t.tenant_id == tenant_a.pk
    assert t.lead_id == oportunidade_a.lead_id


@pytest.mark.django_db
def test_acao_criar_tarefa_cai_no_responsavel_da_oportunidade(tenant_a, oportunidade_a, vendedor):
    """Sem responsavel_id no config, a tarefa vai pro dono da oportunidade."""
    from apps.comercial.crm.models import TarefaCRM
    from apps.comercial.crm.services.automacao_pipeline import _acao_criar_tarefa

    _acao_criar_tarefa(oportunidade_a, {'titulo': 'Ligar pro cliente'})

    t = TarefaCRM.objects.get(oportunidade=oportunidade_a)
    assert t.responsavel_id == vendedor.pk


@pytest.mark.django_db
def test_acao_criar_tarefa_nao_duplica(tenant_a, oportunidade_a):
    """Idempotencia: regra que dispara duas vezes nao gera duas tarefas."""
    from apps.comercial.crm.models import TarefaCRM
    from apps.comercial.crm.services.automacao_pipeline import _acao_criar_tarefa

    config = {'titulo': 'Revisar viabilidade'}

    assert _acao_criar_tarefa(oportunidade_a, config) is True
    assert _acao_criar_tarefa(oportunidade_a, config) is False  # pulou

    assert TarefaCRM.objects.filter(oportunidade=oportunidade_a).count() == 1


@pytest.mark.django_db
def test_acao_criar_tarefa_exige_titulo(tenant_a, oportunidade_a):
    """Sem titulo, a acao recusa em vez de criar tarefa vazia."""
    from apps.comercial.crm.models import TarefaCRM
    from apps.comercial.crm.services.automacao_pipeline import _acao_criar_tarefa

    assert _acao_criar_tarefa(oportunidade_a, {'titulo': '   '}) is False
    assert TarefaCRM.objects.filter(oportunidade=oportunidade_a).count() == 0
