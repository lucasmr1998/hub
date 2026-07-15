"""Varreduras `oportunidades_perdidas` e `oportunidades_paradas` (registry
`apps.automacao.varreduras.VARREDURAS`)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.automacao.varreduras import _oportunidades_paradas, _oportunidades_perdidas
from tests.factories import (
    HistoricoContatoFactory, OportunidadeVendaFactory, PipelineEstagioFactory, TenantFactory, UserFactory,
)


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
def test_filtro_motivo_ref_nome():
    from apps.comercial.crm.models import MotivoPerda

    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    sem_retorno = MotivoPerda.objects.create(tenant=tenant, nome='Sem retorno', ativo=True)
    preco = MotivoPerda.objects.create(tenant=tenant, nome='Preço', ativo=True)
    op_sem_retorno = _op_perdida(tenant, estagio, 40, motivo_perda_ref=sem_retorno)
    op_preco = _op_perdida(tenant, estagio, 40, motivo_perda_ref=preco)

    achados = _oportunidades_perdidas(tenant, {'motivo_ref_nome': 'sem retorno'})  # case insensitive

    ids = {a['oportunidade'].pk for a in achados}
    assert ids == {op_sem_retorno.pk}
    assert op_preco.pk not in ids


@pytest.mark.django_db
def test_estrutura_do_retorno():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    op = _op_perdida(tenant, estagio, 40)

    achados = _oportunidades_perdidas(tenant, {})

    assert len(achados) == 1
    item = achados[0]
    assert set(item.keys()) == {'oportunidade', 'lead', 'dias_perdida', 'motivo_perda_nome'}
    assert item['oportunidade'].pk == op.pk
    assert item['lead'].pk == op.lead_id
    assert item['dias_perdida'] >= 40
    assert item['motivo_perda_nome'] == ''


@pytest.mark.django_db
def test_motivo_perda_nome_no_item_quando_op_tem_motivo_ref():
    from apps.comercial.crm.models import MotivoPerda

    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    motivo = MotivoPerda.objects.create(tenant=tenant, nome='Sem retorno', ativo=True)
    op = _op_perdida(tenant, estagio, 40, motivo_perda_ref=motivo)

    achados = _oportunidades_perdidas(tenant, {})

    assert achados[0]['motivo_perda_nome'] == 'Sem retorno'


# ──────────────────────────────────────────────
# exige_responsavel
# ──────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('valor_config', [True, 'true', 'TRUE', '1', 'sim'])
def test_exige_responsavel_exclui_op_sem_responsavel(valor_config):
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    vendedora = UserFactory()
    com_responsavel = _op_perdida(tenant, estagio, 40, responsavel=vendedora)
    sem_responsavel = _op_perdida(tenant, estagio, 40, responsavel=None)

    achados = _oportunidades_perdidas(tenant, {'exige_responsavel': valor_config})

    ids = {a['oportunidade'].pk for a in achados}
    assert ids == {com_responsavel.pk}
    assert sem_responsavel.pk not in ids


@pytest.mark.django_db
def test_exige_responsavel_desligado_por_padrao_traz_tudo():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    sem_responsavel = _op_perdida(tenant, estagio, 40, responsavel=None)

    achados = _oportunidades_perdidas(tenant, {})

    assert sem_responsavel.pk in {a['oportunidade'].pk for a in achados}


# ──────────────────────────────────────────────
# sem_contato_dias
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_sem_contato_dias_exclui_lead_com_contato_recente():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    op_contato_recente = _op_perdida(tenant, estagio, 40)
    HistoricoContatoFactory(
        tenant=tenant, lead=op_contato_recente.lead,
        data_hora_contato=timezone.now() - timedelta(days=2),
    )
    op_sem_contato = _op_perdida(tenant, estagio, 40)

    achados = _oportunidades_perdidas(tenant, {'sem_contato_dias': 7})

    ids = {a['oportunidade'].pk for a in achados}
    assert ids == {op_sem_contato.pk}
    assert op_contato_recente.pk not in ids


@pytest.mark.django_db
def test_sem_contato_dias_mantem_lead_com_contato_antigo():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    op = _op_perdida(tenant, estagio, 40)
    HistoricoContatoFactory(
        tenant=tenant, lead=op.lead,
        data_hora_contato=timezone.now() - timedelta(days=30),
    )

    achados = _oportunidades_perdidas(tenant, {'sem_contato_dias': 7})

    assert op.pk in {a['oportunidade'].pk for a in achados}


@pytest.mark.django_db
def test_sem_contato_dias_zero_ou_ausente_nao_filtra():
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    op = _op_perdida(tenant, estagio, 40)
    HistoricoContatoFactory(
        tenant=tenant, lead=op.lead, data_hora_contato=timezone.now(),
    )

    achados = _oportunidades_perdidas(tenant, {'sem_contato_dias': 0})

    assert op.pk in {a['oportunidade'].pk for a in achados}


@pytest.mark.django_db
def test_sem_contato_dias_nao_duplica_com_varios_contatos():
    """Lead com múltiplos HistoricoContato antigos (nenhum dentro da janela) não
    pode aparecer duplicado no resultado."""
    tenant = TenantFactory()
    estagio = _estagio_perdido(tenant)
    op = _op_perdida(tenant, estagio, 40)
    for dias_atras in (30, 45, 60):
        HistoricoContatoFactory(
            tenant=tenant, lead=op.lead,
            data_hora_contato=timezone.now() - timedelta(days=dias_atras),
        )

    achados = _oportunidades_perdidas(tenant, {'sem_contato_dias': 7})

    ids = [a['oportunidade'].pk for a in achados]
    assert ids == [op.pk]  # sem duplicatas


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


# ──────────────────────────────────────────────
# _oportunidades_paradas (SLA por etapa, follow-up recorrente pedido pela Gabi)
# ──────────────────────────────────────────────

def _estagio_vivo(tenant, sla_horas=None, **kw):
    return PipelineEstagioFactory(
        tenant=tenant, sla_horas=sla_horas, is_final_perdido=False, is_final_ganho=False, **kw,
    )


def _op_parada(tenant, estagio, horas_atras, **kw):
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio, ativo=True, **kw)
    op.data_entrada_estagio = timezone.now() - timedelta(hours=horas_atras)
    op.save(update_fields=['data_entrada_estagio'])
    return op


@pytest.mark.django_db
def test_paradas_entra_op_alem_do_sla_e_exclui_dentro_do_sla():
    tenant = TenantFactory()
    vendedora = UserFactory()
    estagio = _estagio_vivo(tenant, sla_horas=2)
    alem_do_sla = _op_parada(tenant, estagio, 3, responsavel=vendedora)
    dentro_do_sla = _op_parada(tenant, estagio, 1, responsavel=vendedora)

    achados = _oportunidades_paradas(tenant, {})

    ids = {a['oportunidade'].pk for a in achados}
    assert alem_do_sla.pk in ids
    assert dentro_do_sla.pk not in ids


@pytest.mark.django_db
def test_paradas_ignora_estagio_final_perdido_ou_ganho():
    tenant = TenantFactory()
    vendedora = UserFactory()
    estagio_perdido = PipelineEstagioFactory(tenant=tenant, sla_horas=1, is_final_perdido=True)
    estagio_ganho = PipelineEstagioFactory(tenant=tenant, sla_horas=1, is_final_ganho=True)
    op_perdida = _op_parada(tenant, estagio_perdido, 10, responsavel=vendedora)
    op_ganha = _op_parada(tenant, estagio_ganho, 10, responsavel=vendedora)

    achados = _oportunidades_paradas(tenant, {})

    ids = {a['oportunidade'].pk for a in achados}
    assert op_perdida.pk not in ids
    assert op_ganha.pk not in ids


@pytest.mark.django_db
def test_paradas_apenas_com_sla_ignora_estagio_sem_sla():
    tenant = TenantFactory()
    vendedora = UserFactory()
    estagio_sem_sla = _estagio_vivo(tenant, sla_horas=None)
    _op_parada(tenant, estagio_sem_sla, 100, responsavel=vendedora)

    achados = _oportunidades_paradas(tenant, {'apenas_com_sla': 'true'})

    assert achados == []


@pytest.mark.django_db
def test_paradas_sla_padrao_usado_quando_apenas_com_sla_desligado():
    tenant = TenantFactory()
    vendedora = UserFactory()
    estagio_sem_sla = _estagio_vivo(tenant, sla_horas=None)
    alem_do_padrao = _op_parada(tenant, estagio_sem_sla, 5, responsavel=vendedora)
    dentro_do_padrao = _op_parada(tenant, estagio_sem_sla, 1, responsavel=vendedora)

    achados = _oportunidades_paradas(
        tenant, {'apenas_com_sla': 'false', 'sla_horas_padrao': 2},
    )

    ids = {a['oportunidade'].pk for a in achados}
    assert alem_do_padrao.pk in ids
    assert dentro_do_padrao.pk not in ids


@pytest.mark.django_db
def test_paradas_exige_responsavel_exclui_op_sem_responsavel():
    tenant = TenantFactory()
    estagio = _estagio_vivo(tenant, sla_horas=1)
    vendedora = UserFactory()
    com_responsavel = _op_parada(tenant, estagio, 10, responsavel=vendedora)
    sem_responsavel = _op_parada(tenant, estagio, 10, responsavel=None)

    achados = _oportunidades_paradas(tenant, {})

    ids = {a['oportunidade'].pk for a in achados}
    assert ids == {com_responsavel.pk}
    assert sem_responsavel.pk not in ids


@pytest.mark.django_db
def test_paradas_estrutura_do_item():
    tenant = TenantFactory()
    vendedora = UserFactory()
    estagio = _estagio_vivo(tenant, sla_horas=2, nome='Negociacao', slug='negociacao')
    op = _op_parada(tenant, estagio, 5, responsavel=vendedora)

    achados = _oportunidades_paradas(tenant, {})

    assert len(achados) == 1
    item = achados[0]
    assert set(item.keys()) == {
        'oportunidade', 'lead', 'horas_paradas', 'estagio_nome', 'estagio_atual', 'sla_horas',
    }
    assert item['oportunidade'].pk == op.pk
    assert item['lead'].pk == op.lead_id
    assert item['horas_paradas'] >= 5
    assert item['estagio_nome'] == 'Negociacao'
    assert item['estagio_atual'] == 'negociacao'
    assert item['sla_horas'] == 2


@pytest.mark.django_db
def test_paradas_filtro_estagios_csv_restringe():
    tenant = TenantFactory()
    vendedora = UserFactory()
    estagio_a = _estagio_vivo(tenant, sla_horas=1, slug='estagio-a')
    estagio_b = _estagio_vivo(tenant, sla_horas=1, slug='estagio-b')
    op_a = _op_parada(tenant, estagio_a, 10, responsavel=vendedora)
    op_b = _op_parada(tenant, estagio_b, 10, responsavel=vendedora)

    achados = _oportunidades_paradas(tenant, {'estagios': 'estagio-a'})

    ids = {a['oportunidade'].pk for a in achados}
    assert ids == {op_a.pk}
    assert op_b.pk not in ids


@pytest.mark.django_db
def test_paradas_max_ordem_restringe():
    tenant = TenantFactory()
    vendedora = UserFactory()
    estagio_1 = _estagio_vivo(tenant, sla_horas=1, ordem=1)
    estagio_5 = _estagio_vivo(tenant, sla_horas=1, ordem=5)
    op_1 = _op_parada(tenant, estagio_1, 10, responsavel=vendedora)
    op_5 = _op_parada(tenant, estagio_5, 10, responsavel=vendedora)

    achados = _oportunidades_paradas(tenant, {'max_ordem': 2})

    ids = {a['oportunidade'].pk for a in achados}
    assert ids == {op_1.pk}
    assert op_5.pk not in ids
