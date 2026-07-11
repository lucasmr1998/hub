"""Testes da re-hidratação de entidades no caminho da fila (enfileirar → cron).

Prova o fix: `_enfileirar` persiste as entidades por id (`Contexto.serializar`)
e `_rehidratar` restaura `oportunidade` (e lead via fallback), permitindo que
nós de CRM rodem no caminho deferido (`rodar_novos`)."""
import pytest
from django.utils import timezone

from apps.automacao.execucao import _rehidratar, rodar_novos
from apps.automacao.gatilhos import _enfileirar
from apps.automacao.models import ExecucaoFluxo, Fluxo
from apps.automacao.nodes import Contexto

pytestmark = pytest.mark.django_db


def _cenario():
    """Tenant + pipeline + estágio + lead + op mínimos (padrão dos testes com DB)."""
    from apps.comercial.crm.models import Pipeline, PipelineEstagio, OportunidadeVenda
    from apps.comercial.leads.models import LeadProspecto
    from apps.sistema.models import Tenant

    tenant = Tenant.objects.create(nome='T Rehidrata', slug='t-rehidrata')
    pipeline = Pipeline.all_tenants.create(tenant=tenant, nome='P', slug='p', padrao=True)
    estagio = PipelineEstagio.all_tenants.create(
        tenant=tenant, pipeline=pipeline, nome='Novo', slug='novo', ordem=1)
    lead = LeadProspecto.all_tenants.create(
        tenant=tenant, nome_razaosocial='Lead X', telefone='5511999990000')
    op = OportunidadeVenda.all_tenants.create(
        tenant=tenant, lead=lead, pipeline=pipeline, estagio=estagio, titulo='Op X')
    return tenant, lead, op


def _fluxo_nota(tenant):
    """Fluxo mínimo com um nó de CRM que EXIGE contexto.oportunidade."""
    grafo = {
        'inicio': 'trigger',
        'nodes': {
            'trigger': {'tipo': 'webhook', 'config': {}},
            'nota': {'tipo': 'criar_nota', 'config': {'texto': 'nota da fila'}},
        },
        'conexoes': [{'de': 'trigger', 'para': 'nota', 'saida': 'default'}],
    }
    return Fluxo.all_tenants.create(tenant=tenant, nome='F rehidrata', grafo=grafo, ativo=True)


def test_enfileirar_persiste_entidades():
    tenant, lead, op = _cenario()
    fluxo = _fluxo_nota(tenant)
    ctx = Contexto(tenant=tenant, lead=lead, oportunidade=op, variaveis={'x': 1})
    _enfileirar(fluxo, ctx, 'trigger')
    ex = ExecucaoFluxo.all_tenants.get(fluxo=fluxo)
    ents = (ex.estado or {}).get('entidades') or {}
    assert ents.get('oportunidade') == op.pk
    assert ents.get('lead') == lead.pk
    assert ex.estado.get('inicio') == 'trigger'


def test_rehidratar_restaura_oportunidade():
    tenant, lead, op = _cenario()
    fluxo = _fluxo_nota(tenant)
    ctx = Contexto(tenant=tenant, lead=lead, oportunidade=op)
    _enfileirar(fluxo, ctx, 'trigger')
    ex = ExecucaoFluxo.all_tenants.get(fluxo=fluxo)
    contexto = _rehidratar(ex)
    assert contexto.oportunidade is not None and contexto.oportunidade.pk == op.pk
    assert contexto.lead is not None and contexto.lead.pk == lead.pk


def test_caminho_da_fila_completo_roda_no_de_crm():
    """enfileirar → rodar_novos → criar_nota funciona (a lacuna que travava tudo)."""
    from apps.comercial.crm.models import NotaInterna
    from django.contrib.auth.models import User

    tenant, lead, op = _cenario()
    # autor default da nota precisa existir (superuser fallback)
    User.objects.create_superuser('root-rehidrata', 'r@x.com', 'x')
    fluxo = _fluxo_nota(tenant)
    ctx = Contexto(tenant=tenant, lead=lead, oportunidade=op)
    _enfileirar(fluxo, ctx, 'trigger')
    ExecucaoFluxo.all_tenants.filter(fluxo=fluxo).update(agendado_para=timezone.now())

    n = rodar_novos()
    assert n == 1
    ex = ExecucaoFluxo.all_tenants.get(fluxo=fluxo)
    assert ex.status == 'completado', ex.erro
    assert NotaInterna.all_tenants.filter(tenant=tenant, oportunidade=op).exists()


def test_rehidratar_sem_entidades_nao_quebra():
    tenant, lead, op = _cenario()
    fluxo = _fluxo_nota(tenant)
    ex = ExecucaoFluxo.all_tenants.create(
        tenant=tenant, fluxo=fluxo, status='pendente',
        estado={'variaveis': {}, 'nodes': {}, 'inicio': 'trigger'})
    contexto = _rehidratar(ex)
    assert contexto.oportunidade is None and contexto.conversa is None
