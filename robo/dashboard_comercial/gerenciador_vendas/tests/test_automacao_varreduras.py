"""Varredura `oportunidades_perdidas` (registry `apps.automacao.varreduras.VARREDURAS`)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.automacao.varreduras import _oportunidades_perdidas
from tests.factories import OportunidadeVendaFactory, PipelineEstagioFactory, TenantFactory


def _estagio_perdido(tenant, **kw):
    return PipelineEstagioFactory(tenant=tenant, is_final_perdido=True, tipo='perdido', **kw)


def _op_perdida(tenant, estagio, dias_atras, **kw):
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio, ativo=True, **kw)
    op.data_fechamento_real = timezone.now() - timedelta(days=dias_atras)
    op.save(update_fields=['data_fechamento_real'])
    return op


@pytest.mark.django_db
def test_janela_dias_min_default_filtra_dentro_e_fora():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    fora_da_janela = _op_perdida(tenant, estagio, 45)  # perdida há 45d >= 30d default => entra
    recente_demais = _op_perdida(tenant, estagio, 5)   # perdida há 5d < 30d default => não entra

    achados = _oportunidades_perdidas(tenant, {})

    ids = {a['oportunidade'].pk for a in achados}
    assert fora_da_janela.pk in ids
    assert recente_demais.pk not in ids


@pytest.mark.django_db
def test_janela_dias_min_configuravel():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    op = _op_perdida(tenant, estagio, 10)

    assert _oportunidades_perdidas(tenant, {'janela_dias_min': 30}) == []

    achados = _oportunidades_perdidas(tenant, {'janela_dias_min': 5})
    assert {a['oportunidade'].pk for a in achados} == {op.pk}


@pytest.mark.django_db
def test_filtro_motivo_categoria():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    preco = _op_perdida(tenant, estagio, 40, motivo_perda_categoria='preco')
    timing = _op_perdida(tenant, estagio, 40, motivo_perda_categoria='timing')

    achados = _oportunidades_perdidas(tenant, {'motivo_categoria': 'preco'})

    ids = {a['oportunidade'].pk for a in achados}
    assert ids == {preco.pk}
    assert timing.pk not in ids


@pytest.mark.django_db
def test_sem_marcador_exclui_ja_processadas():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    nova = _op_perdida(tenant, estagio, 40)
    ja_processada = _op_perdida(tenant, estagio, 40, dados_custom={'analise_perda': True})

    achados = _oportunidades_perdidas(tenant, {'sem_marcador': 'analise_perda'})

    ids = {a['oportunidade'].pk for a in achados}
    assert ids == {nova.pk}
    assert ja_processada.pk not in ids


@pytest.mark.django_db
def test_estrutura_do_retorno():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    op = _op_perdida(tenant, estagio, 40)

    achados = _oportunidades_perdidas(tenant, {})

    assert len(achados) == 1
    item = achados[0]
    assert set(item.keys()) == {'oportunidade', 'lead', 'dias_perdida'}
    assert item['oportunidade'].pk == op.pk
    assert item['lead'].pk == op.lead_id
    assert item['dias_perdida'] >= 40


@pytest.mark.django_db
def test_ignora_oportunidades_nao_perdidas_ou_sem_data_fechamento():
    tenant = TenantFactory()
    estagio_aberto = PipelineEstagioFactory(tenant=tenant, is_final_perdido=False)
    aberta = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_aberto, ativo=True)

    estagio_perdido = _estagio_perdido(tenant)
    sem_data = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_perdido, ativo=True)

    achados = _oportunidades_perdidas(tenant, {})

    ids = {a['oportunidade'].pk for a in achados}
    assert aberta.pk not in ids
    assert sem_data.pk not in ids
