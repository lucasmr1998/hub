"""Testes do nó `definir_propriedade_oportunidade` + registry
`propriedades_oportunidade.py` (com DB, os handlers tocam o ORM direto).

Cobre a REDE DE SEGURANÇA achada no piloto do fluxo 25: motivo de perda fora
do catálogo ou oportunidade fora de estágio de perda nunca vira exceção
(seria erro determinístico → retry inútil); vira sempre um branch de
SUCESSO com `aplicado=False` + `motivo_skip`.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.automacao.nodes import Contexto, tipo_por_slug
from apps.comercial.crm.models import MotivoPerda
from tests.factories import OportunidadeVendaFactory, PipelineEstagioFactory, TenantFactory


def _ctx(tenant, **kwargs):
    return Contexto(tenant=tenant, **kwargs)


def _no():
    return tipo_por_slug('definir_propriedade_oportunidade')


def test_registrado():
    assert _no() is not None


def test_validar_config_exige_propriedade_valida():
    no = _no()
    assert no.validar_config({'propriedade': 'motivo_perda'}) == []
    assert no.validar_config({'propriedade': 'nao_existe'}) != []
    assert no.validar_config({}) != []


def test_sem_oportunidade_vira_erro():
    tenant = SimpleNamespace(pk=1, slug='alpha')
    res = _no().executar({'propriedade': 'marcador', 'chave': 'x'}, {}, _ctx(tenant))
    assert res.branch == 'erro'
    assert 'oportunidade' in (res.erro or '').lower()


def test_propriedade_desconhecida_vira_erro():
    tenant = SimpleNamespace(pk=1, slug='alpha')
    op = SimpleNamespace(pk=7)
    res = _no().executar({'propriedade': 'nao_existe'}, {}, _ctx(tenant, oportunidade=op))
    assert res.branch == 'erro'
    assert 'desconhecida' in (res.erro or '').lower()


# ──────────────────────────────────────────────
# motivo_perda
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_motivo_perda_aplica_quando_op_esta_perdida():
    tenant = TenantFactory()
    motivo = MotivoPerda.objects.create(tenant=tenant, nome='Preço alto', ativo=True)
    estagio_perdido = PipelineEstagioFactory(tenant=tenant, is_final_perdido=True, tipo='perdido')
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_perdido)

    res = _no().executar(
        {'propriedade': 'motivo_perda', 'valor': ' preço alto '}, {}, _ctx(tenant, oportunidade=op))

    assert res.status == 'ok'
    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is True
    assert res.output['motivo_skip'] is None
    assert res.output['propriedade'] == 'motivo_perda'
    op.refresh_from_db()
    assert op.motivo_perda_ref_id == motivo.pk


@pytest.mark.django_db
def test_motivo_perda_op_nao_perdida_pula_sem_erro():
    """REDE DE SEGURANÇA (achado piloto fluxo 25): nunca poluir op aberta com motivo de perda."""
    tenant = TenantFactory()
    MotivoPerda.objects.create(tenant=tenant, nome='Preço alto', ativo=True)
    estagio_aberto = PipelineEstagioFactory(tenant=tenant, is_final_perdido=False)
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_aberto)

    res = _no().executar(
        {'propriedade': 'motivo_perda', 'valor': 'Preço alto'}, {}, _ctx(tenant, oportunidade=op))

    assert res.status == 'ok'  # sucesso: skip não é erro
    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is False
    assert res.output['motivo_skip'] == 'op_nao_perdida'
    op.refresh_from_db()
    assert op.motivo_perda_ref_id is None


@pytest.mark.django_db
def test_motivo_perda_inexistente_no_catalogo_pula_sem_erro_sem_retry():
    """Achado piloto fluxo 25: agente IA inventou motivo fora do catálogo. O nó
    antigo levantava ValueError (erro determinístico -> retry inútil); agora é
    skip, status 'ok', sem acionar retry."""
    tenant = TenantFactory()
    MotivoPerda.objects.create(tenant=tenant, nome='Timing', ativo=True)
    estagio_perdido = PipelineEstagioFactory(tenant=tenant, is_final_perdido=True, tipo='perdido')
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_perdido)

    res = _no().executar(
        {'propriedade': 'motivo_perda', 'valor': 'Motivo Inventado Pelo Agente'}, {},
        _ctx(tenant, oportunidade=op))

    assert res.status == 'ok'
    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is False
    assert res.output['motivo_skip'] == 'motivo_nao_encontrado'
    assert 'Timing' in res.output['detalhe']  # lista os disponíveis
    op.refresh_from_db()
    assert op.motivo_perda_ref_id is None


@pytest.mark.django_db
def test_motivo_perda_somente_se_vazio_true_default_pula_quando_ja_tem():
    tenant = TenantFactory()
    motivo_atual = MotivoPerda.objects.create(tenant=tenant, nome='Timing', ativo=True)
    MotivoPerda.objects.create(tenant=tenant, nome='Preço', ativo=True)
    estagio_perdido = PipelineEstagioFactory(tenant=tenant, is_final_perdido=True, tipo='perdido')
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_perdido, motivo_perda_ref=motivo_atual)

    res = _no().executar(
        {'propriedade': 'motivo_perda', 'valor': 'Preço'}, {}, _ctx(tenant, oportunidade=op))

    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is False
    assert res.output['motivo_skip'] == 'ja_tinha'
    op.refresh_from_db()
    assert op.motivo_perda_ref_id == motivo_atual.pk  # não trocou


@pytest.mark.django_db
def test_motivo_perda_somente_se_vazio_false_explicito_sobrescreve():
    tenant = TenantFactory()
    motivo_atual = MotivoPerda.objects.create(tenant=tenant, nome='Timing', ativo=True)
    motivo_novo = MotivoPerda.objects.create(tenant=tenant, nome='Preço', ativo=True)
    estagio_perdido = PipelineEstagioFactory(tenant=tenant, is_final_perdido=True, tipo='perdido')
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_perdido, motivo_perda_ref=motivo_atual)

    res = _no().executar(
        {'propriedade': 'motivo_perda', 'valor': 'Preço', 'somente_se_vazio': False}, {},
        _ctx(tenant, oportunidade=op))

    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is True
    op.refresh_from_db()
    assert op.motivo_perda_ref_id == motivo_novo.pk


# ──────────────────────────────────────────────
# marcador
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_marcador_sem_chave_pula_sem_erro():
    tenant = TenantFactory()
    op = OportunidadeVendaFactory(tenant=tenant)

    res = _no().executar({'propriedade': 'marcador', 'valor': 'x'}, {}, _ctx(tenant, oportunidade=op))

    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is False
    assert res.output['motivo_skip'] == 'sem_chave'


@pytest.mark.django_db
def test_marcador_sem_valor_grava_timestamp():
    tenant = TenantFactory()
    op = OportunidadeVendaFactory(tenant=tenant, dados_custom={'existente': 'valor'})

    res = _no().executar(
        {'propriedade': 'marcador', 'chave': 'analise_perda'}, {}, _ctx(tenant, oportunidade=op))

    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is True
    op.refresh_from_db()
    assert 'T' in op.dados_custom['analise_perda']  # timestamp ISO 8601
    assert op.dados_custom['existente'] == 'valor'  # não perde dado anterior


@pytest.mark.django_db
def test_marcador_com_chave_e_valor_explicito():
    tenant = TenantFactory()
    op = OportunidadeVendaFactory(tenant=tenant)

    res = _no().executar(
        {'propriedade': 'marcador', 'chave': 'recuperacao_enviada', 'valor': 'sim'}, {},
        _ctx(tenant, oportunidade=op))

    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is True
    op.refresh_from_db()
    assert op.dados_custom['recuperacao_enviada'] == 'sim'


# ──────────────────────────────────────────────
# valor_estimado
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_valor_estimado_invalido_pula_sem_erro():
    tenant = TenantFactory()
    op = OportunidadeVendaFactory(tenant=tenant)

    res = _no().executar(
        {'propriedade': 'valor_estimado', 'valor': 'nao-e-numero'}, {}, _ctx(tenant, oportunidade=op))

    assert res.status == 'ok'
    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is False
    assert res.output['motivo_skip'] == 'valor_invalido'


@pytest.mark.django_db
def test_valor_estimado_valido_aplica():
    tenant = TenantFactory()
    op = OportunidadeVendaFactory(tenant=tenant)

    res = _no().executar(
        {'propriedade': 'valor_estimado', 'valor': '150,50'}, {}, _ctx(tenant, oportunidade=op))

    assert res.branch == 'sucesso'
    assert res.output['aplicado'] is True
    op.refresh_from_db()
    assert op.valor_estimado_manual == Decimal('150.50')
