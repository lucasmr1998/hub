"""Testes com DB dos services de CRM em `acoes.py`: `criar_nota`,
`definir_motivo_perda`, `reabrir_oportunidade`, `marcar_dados_custom`."""
import pytest
from django.utils import timezone

from apps.automacao.services.acoes import (
    criar_nota,
    definir_motivo_perda,
    marcar_dados_custom,
    reabrir_oportunidade,
)
from apps.comercial.crm.models import HistoricoPipelineEstagio, MotivoPerda, NotaInterna
from apps.sistema.models import PerfilUsuario
from tests.factories import OportunidadeVendaFactory, PipelineEstagioFactory, TenantFactory, UserFactory


# ──────────────────────────────────────────────
# criar_nota
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_criar_nota_cria_nota_interna_vinculada_a_op():
    tenant = TenantFactory()
    responsavel = UserFactory()
    op = OportunidadeVendaFactory(tenant=tenant, responsavel=responsavel)

    nota = criar_nota(tenant, oportunidade=op, texto='Cliente pediu desconto', titulo='Negociação')

    assert isinstance(nota, NotaInterna)
    assert nota.pk is not None
    assert nota.oportunidade_id == op.pk
    assert nota.tenant_id == tenant.pk
    assert nota.autor_id == responsavel.pk
    assert 'Negociação' in nota.conteudo
    assert 'Cliente pediu desconto' in nota.conteudo


@pytest.mark.django_db
def test_criar_nota_sem_responsavel_usa_staff_do_tenant():
    tenant = TenantFactory()
    staff = UserFactory(is_staff=True)
    PerfilUsuario.objects.create(tenant=tenant, user=staff)
    op = OportunidadeVendaFactory(tenant=tenant, responsavel=None)

    nota = criar_nota(tenant, oportunidade=op, texto='Nota sem responsável na op')

    assert nota.autor_id == staff.pk


# ──────────────────────────────────────────────
# definir_motivo_perda
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_definir_motivo_perda_resolve_por_nome_iexact():
    tenant = TenantFactory()
    motivo = MotivoPerda.objects.create(tenant=tenant, nome='Preço alto', ativo=True)
    op = OportunidadeVendaFactory(tenant=tenant)

    resolvido, alterou = definir_motivo_perda(tenant, oportunidade=op, motivo_nome='  preço alto  ')

    op.refresh_from_db()
    assert alterou is True
    assert resolvido.pk == motivo.pk
    assert op.motivo_perda_ref_id == motivo.pk


@pytest.mark.django_db
def test_definir_motivo_perda_somente_se_vazio_pula_quando_ja_tem():
    tenant = TenantFactory()
    motivo_atual = MotivoPerda.objects.create(tenant=tenant, nome='Timing', ativo=True)
    MotivoPerda.objects.create(tenant=tenant, nome='Preço', ativo=True)
    op = OportunidadeVendaFactory(tenant=tenant, motivo_perda_ref=motivo_atual)

    resolvido, alterou = definir_motivo_perda(tenant, oportunidade=op, motivo_nome='Preço')

    op.refresh_from_db()
    assert alterou is False
    assert resolvido.pk == motivo_atual.pk
    assert op.motivo_perda_ref_id == motivo_atual.pk  # não trocou


@pytest.mark.django_db
def test_definir_motivo_perda_motivo_inexistente_levanta_value_error():
    tenant = TenantFactory()
    MotivoPerda.objects.create(tenant=tenant, nome='Timing', ativo=True)
    op = OportunidadeVendaFactory(tenant=tenant)

    with pytest.raises(ValueError):
        definir_motivo_perda(tenant, oportunidade=op, motivo_nome='Inexistente')


# ──────────────────────────────────────────────
# reabrir_oportunidade
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_reabrir_oportunidade_so_reabre_de_estagio_perdido():
    tenant = TenantFactory()
    estagio_aberto = PipelineEstagioFactory(tenant=tenant, is_final_perdido=False)
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_aberto)

    estagio_novo, reabriu = reabrir_oportunidade(tenant, oportunidade=op, estagio_slug='negociacao')

    assert reabriu is False
    assert estagio_novo is None


@pytest.mark.django_db
def test_reabrir_oportunidade_cria_historico_limpa_fechamento_e_mantem_auditoria():
    tenant = TenantFactory()
    responsavel = UserFactory()
    motivo = MotivoPerda.objects.create(tenant=tenant, nome='Preço', ativo=True)
    estagio_perdido = PipelineEstagioFactory(tenant=tenant, is_final_perdido=True, tipo='perdido')
    estagio_negociacao = PipelineEstagioFactory(tenant=tenant, slug='negociacao', is_final_perdido=False)
    op = OportunidadeVendaFactory(
        tenant=tenant, estagio=estagio_perdido, responsavel=responsavel,
        motivo_perda='Cliente achou caro', motivo_perda_ref=motivo,
    )
    op.data_fechamento_real = timezone.now()
    op.save(update_fields=['data_fechamento_real'])

    estagio_novo, reabriu = reabrir_oportunidade(
        tenant, oportunidade=op, estagio_slug='negociacao', motivo='Cliente voltou a negociar')

    op.refresh_from_db()
    assert reabriu is True
    assert estagio_novo.pk == estagio_negociacao.pk
    assert op.estagio_id == estagio_negociacao.pk
    assert op.data_fechamento_real is None
    # auditoria da perda anterior mantida
    assert op.motivo_perda == 'Cliente achou caro'
    assert op.motivo_perda_ref_id == motivo.pk
    assert op.responsavel_id == responsavel.pk

    historico = HistoricoPipelineEstagio.objects.filter(oportunidade=op).first()
    assert historico is not None
    assert historico.estagio_anterior_id == estagio_perdido.pk
    assert historico.estagio_novo_id == estagio_negociacao.pk
    assert 'Cliente voltou a negociar' in historico.motivo


@pytest.mark.django_db
def test_reabrir_oportunidade_estagio_inexistente_levanta_value_error():
    tenant = TenantFactory()
    estagio_perdido = PipelineEstagioFactory(tenant=tenant, is_final_perdido=True, tipo='perdido')
    op = OportunidadeVendaFactory(tenant=tenant, estagio=estagio_perdido)

    with pytest.raises(ValueError):
        reabrir_oportunidade(tenant, oportunidade=op, estagio_slug='nao-existe')


# ──────────────────────────────────────────────
# marcar_dados_custom
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_marcar_dados_custom_grava_timestamp_default():
    tenant = TenantFactory()
    op = OportunidadeVendaFactory(tenant=tenant, dados_custom={'existente': 'valor'})

    valor_gravado = marcar_dados_custom(tenant, oportunidade=op, chave='analise_perda')

    op.refresh_from_db()
    assert isinstance(valor_gravado, str) and 'T' in valor_gravado  # ISO 8601
    assert op.dados_custom['analise_perda'] == valor_gravado
    assert op.dados_custom['existente'] == 'valor'  # não perde dado anterior


@pytest.mark.django_db
def test_marcar_dados_custom_grava_valor_explicito():
    tenant = TenantFactory()
    op = OportunidadeVendaFactory(tenant=tenant)

    valor_gravado = marcar_dados_custom(tenant, oportunidade=op, chave='score', valor=42)

    op.refresh_from_db()
    assert valor_gravado == 42
    assert op.dados_custom['score'] == 42
