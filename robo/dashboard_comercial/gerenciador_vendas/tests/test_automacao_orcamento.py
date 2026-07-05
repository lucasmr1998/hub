"""
Testes do orçamento global anti-loop (hardening E5).

Cobre `_orcamento_excedido`: teto default-on de execuções por hora, por lead e
por fluxo inteiro, independente do freio opcional (`_freio_bloqueia`) e do
guard de profundidade thread-local (que só protege dentro do mesmo request).
"""
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.automacao.gatilhos import _orcamento_excedido
from apps.automacao.models import ExecucaoFluxo, Fluxo
from apps.sistema.models import LogSistema
from tests.factories import LeadProspectoFactory, TenantFactory


def _fluxo(tenant):
    """Fluxo mínimo (só o gatilho webhook) — o grafo não importa pro orçamento."""
    return Fluxo.objects.create(
        tenant=tenant, nome='Fluxo E5', ativo=True,
        grafo={'inicio': 't', 'nodes': {'t': {'tipo': 'webhook', 'config': {}}}, 'conexoes': []},
    )


def _criar_execucoes(tenant, fluxo, lead, quantidade, *, criado_em=None):
    execucoes = [
        ExecucaoFluxo.all_tenants.create(tenant=tenant, fluxo=fluxo, lead=lead, status='completado')
        for _ in range(quantidade)
    ]
    if criado_em is not None:
        ExecucaoFluxo.all_tenants.filter(
            pk__in=[e.pk for e in execucoes]
        ).update(criado_em=criado_em)
    return execucoes


@pytest.mark.django_db
@override_settings(AUTOMACAO_ORCAMENTO_LEAD_HORA=3, AUTOMACAO_ORCAMENTO_FLUXO_HORA=500)
def test_orcamento_lead_barra_quando_atinge_teto():
    tenant = TenantFactory()
    fluxo = _fluxo(tenant)
    lead = LeadProspectoFactory(tenant=tenant)

    _criar_execucoes(tenant, fluxo, lead, 3)  # já no teto (3)

    assert _orcamento_excedido(fluxo, lead) is True
    assert LogSistema.all_tenants.filter(
        tenant=tenant, acao='automacao_freio_global', entidade_id=fluxo.pk,
    ).exists()


@pytest.mark.django_db
@override_settings(AUTOMACAO_ORCAMENTO_LEAD_HORA=3, AUTOMACAO_ORCAMENTO_FLUXO_HORA=500)
def test_orcamento_lead_libera_abaixo_do_teto():
    tenant = TenantFactory()
    fluxo = _fluxo(tenant)
    lead = LeadProspectoFactory(tenant=tenant)

    _criar_execucoes(tenant, fluxo, lead, 2)  # abaixo do teto (3)

    assert _orcamento_excedido(fluxo, lead) is False
    assert not LogSistema.all_tenants.filter(
        tenant=tenant, acao='automacao_freio_global', entidade_id=fluxo.pk,
    ).exists()


@pytest.mark.django_db
@override_settings(AUTOMACAO_ORCAMENTO_LEAD_HORA=0, AUTOMACAO_ORCAMENTO_FLUXO_HORA=3)
def test_orcamento_fluxo_barra_quando_atinge_teto_mesmo_sem_lead():
    tenant = TenantFactory()
    fluxo = _fluxo(tenant)

    _criar_execucoes(tenant, fluxo, None, 3)  # já no teto (3), execuções sem lead

    assert _orcamento_excedido(fluxo, None) is True
    assert LogSistema.all_tenants.filter(
        tenant=tenant, acao='automacao_freio_global', entidade_id=fluxo.pk,
    ).exists()


@pytest.mark.django_db
@override_settings(AUTOMACAO_ORCAMENTO_LEAD_HORA=3, AUTOMACAO_ORCAMENTO_FLUXO_HORA=500)
def test_orcamento_ignora_execucoes_antigas():
    tenant = TenantFactory()
    fluxo = _fluxo(tenant)
    lead = LeadProspectoFactory(tenant=tenant)

    # 3 execuções, mas de mais de 1h atrás (fora da janela) — não conta pro teto.
    antigo = timezone.now() - timedelta(hours=2)
    _criar_execucoes(tenant, fluxo, lead, 3, criado_em=antigo)

    assert _orcamento_excedido(fluxo, lead) is False
    assert not LogSistema.all_tenants.filter(
        tenant=tenant, acao='automacao_freio_global', entidade_id=fluxo.pk,
    ).exists()


@pytest.mark.django_db
@override_settings(AUTOMACAO_ORCAMENTO_LEAD_HORA=0, AUTOMACAO_ORCAMENTO_FLUXO_HORA=0)
def test_orcamento_desligado_sempre_libera():
    tenant = TenantFactory()
    fluxo = _fluxo(tenant)
    lead = LeadProspectoFactory(tenant=tenant)

    _criar_execucoes(tenant, fluxo, lead, 50)  # muito acima de qualquer teto razoável

    assert _orcamento_excedido(fluxo, lead) is False
    assert _orcamento_excedido(fluxo, None) is False
