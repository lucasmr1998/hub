"""Varredura `oportunidades_perdidas` (registry `apps.automacao.varreduras.VARREDURAS`)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.automacao.varreduras import _oportunidades_perdidas
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
