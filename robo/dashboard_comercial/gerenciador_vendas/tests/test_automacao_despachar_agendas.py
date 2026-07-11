"""
Dispatcher do gatilho `agenda` (varredura) — `gatilhos.despachar_agendas` +
`_rodar_agenda_do_fluxo`.

Cobre: kill-switch, enfileiramento respeitando `max_por_rodada`, CAS anti dupla
rodada, guard "sem freio" e o freio `max_por_lead`, e a sincronização de
`Fluxo.agenda_intervalo_minutos` no `save()`.
"""
from datetime import timedelta
from unittest import mock

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.automacao.gatilhos import _rodar_agenda_do_fluxo, despachar_agendas
from apps.automacao.models import ExecucaoFluxo, Fluxo
from tests.factories import LeadProspectoFactory, TenantFactory


def _grafo_agenda(*, varredura='fake', intervalo=30, max_por_lead=1,
                   cooldown_horas=0, max_por_rodada=None, varredura_config=None):
    cfg = {
        'intervalo_minutos': intervalo,
        'varredura': varredura,
        'varredura_config': varredura_config or {},
        'max_por_lead': max_por_lead,
        'cooldown_horas': cooldown_horas,
    }
    if max_por_rodada is not None:
        cfg['max_por_rodada'] = max_por_rodada
    return {'inicio': 'a1', 'nodes': {'a1': {'tipo': 'agenda', 'config': cfg}}, 'conexoes': []}


def _fluxo(tenant, **kw):
    """Fluxo só com o gatilho `agenda` (varredura chamada 'fake', mockada nos testes)."""
    return Fluxo.objects.create(
        tenant=tenant, nome='Fluxo agenda', ativo=True, grafo=_grafo_agenda(**kw),
    )


@pytest.mark.django_db
@override_settings(AUTOMACAO_WIRING_ATIVO=False)
def test_wiring_off_nao_despacha():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    _fluxo(tenant)

    with mock.patch.dict('apps.automacao.varreduras.VARREDURAS', {'fake': lambda t, c: [{'lead': lead}]}):
        assert despachar_agendas() == 0
    assert ExecucaoFluxo.all_tenants.count() == 0


@pytest.mark.django_db
def test_fluxo_vencido_enfileira_respeitando_max_por_rodada():
    tenant = TenantFactory()
    lead1 = LeadProspectoFactory(tenant=tenant)
    lead2 = LeadProspectoFactory(tenant=tenant)
    fluxo = _fluxo(tenant, max_por_rodada=1)

    fake_itens = [{'lead': lead1}, {'lead': lead2}]
    with mock.patch.dict('apps.automacao.varreduras.VARREDURAS', {'fake': lambda t, c: fake_itens}):
        total = despachar_agendas()

    assert total == 1
    assert ExecucaoFluxo.all_tenants.filter(tenant=tenant, fluxo=fluxo).count() == 1
    fluxo.refresh_from_db()
    assert fluxo.agenda_ultima_rodada is not None


@pytest.mark.django_db
def test_corrida_cas_segunda_chamada_com_mesmo_objeto_nao_reprocessa():
    """Duas chamadas sobre o MESMO objeto `fluxo` (não recarregado do banco entre
    elas) simulam a corrida: a segunda perde o CAS porque a primeira já avançou
    `agenda_ultima_rodada` no banco (o objeto em memória não sabe disso)."""
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    fluxo = _fluxo(tenant)
    agora = timezone.now()

    with mock.patch.dict('apps.automacao.varreduras.VARREDURAS', {'fake': lambda t, c: [{'lead': lead}]}):
        primeira = _rodar_agenda_do_fluxo(fluxo, agora)
        segunda = _rodar_agenda_do_fluxo(fluxo, agora)

    assert primeira == 1
    assert segunda == 0
    assert ExecucaoFluxo.all_tenants.filter(tenant=tenant, fluxo=fluxo).count() == 1


@pytest.mark.django_db
def test_sem_freio_pula_rodada_e_nao_enfileira():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    _fluxo(tenant, max_por_lead=0, cooldown_horas=0)

    chamou_varredura = mock.Mock(return_value=[{'lead': lead}])
    with mock.patch.dict('apps.automacao.varreduras.VARREDURAS', {'fake': chamou_varredura}):
        total = despachar_agendas()

    assert total == 0
    assert ExecucaoFluxo.all_tenants.count() == 0
    chamou_varredura.assert_not_called()  # nem chega a rodar a varredura sem freio


@pytest.mark.django_db
def test_freio_max_por_lead_bloqueia_segunda_rodada_pro_mesmo_lead():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    fluxo = _fluxo(tenant, intervalo=1, max_por_lead=1)

    with mock.patch.dict('apps.automacao.varreduras.VARREDURAS', {'fake': lambda t, c: [{'lead': lead}]}):
        primeira = despachar_agendas()
        # Força o intervalo (1min) já ter vencido pra próxima rodada.
        Fluxo.all_tenants.filter(pk=fluxo.pk).update(
            agenda_ultima_rodada=timezone.now() - timedelta(minutes=5))
        segunda = despachar_agendas()

    assert primeira == 1
    assert segunda == 0  # mesmo lead já tem 1 execução => freio bloqueia
    assert ExecucaoFluxo.all_tenants.filter(tenant=tenant, fluxo=fluxo, lead=lead).count() == 1


@pytest.mark.django_db
def test_fluxo_save_sincroniza_agenda_intervalo_minutos():
    tenant = TenantFactory()
    fluxo = Fluxo.objects.create(tenant=tenant, nome='Sem agenda', ativo=True, grafo={})
    assert fluxo.agenda_intervalo_minutos is None

    fluxo.grafo = _grafo_agenda(intervalo=45)
    fluxo.save()
    fluxo.refresh_from_db()
    assert fluxo.agenda_intervalo_minutos == 45

    fluxo.grafo = {}
    fluxo.save()
    fluxo.refresh_from_db()
    assert fluxo.agenda_intervalo_minutos is None
