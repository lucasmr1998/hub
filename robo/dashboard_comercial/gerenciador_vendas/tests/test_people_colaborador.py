"""
Testes do model `Colaborador`: guarda da situacao, constraints de CPF e soft
delete.

Estes tres assuntos sao a fundacao do modulo inteiro, e todos falham de um jeito
silencioso quando quebram: a guarda deixa passar transicao sem historico, a
unique de CPF deixa nascer pessoa duplicada, e o delete apaga historico de
feedback junto. Por isso cada um tem teste proprio aqui, e nao so o caminho
feliz.
"""
import pytest
from django.db import IntegrityError, transaction

from apps.people import estados
from apps.people.excecoes import PeopleError, TransicaoNaoAutorizada
from apps.people.models import Colaborador, HistoricoSituacao, Unidade, sem_guarda_de_situacao
from tests.factories import TenantFactory


@pytest.fixture
def unidade(db):
    tenant = TenantFactory()
    return Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro', codigo='loja-centro')


def _criar(unidade, nome='Maria Souza', **kwargs):
    return Colaborador.all_tenants.create(
        tenant=unidade.tenant, unidade=unidade, nome_completo=nome, **kwargs,
    )


# ──────────────────────────────────────────────
# Normalizacao de CPF
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cpf_e_normalizado_pra_so_digitos(unidade):
    col = _criar(unidade, cpf='123.456.789-01')
    assert col.cpf == '12345678901'


@pytest.mark.django_db
def test_cpf_incompleto_vira_none_e_nao_string_vazia(unidade):
    """
    A unique de CPF so funciona porque ausente e NULL. Se virasse '', a segunda
    pessoa sem CPF colidiria com a primeira.
    """
    col = _criar(unidade, cpf='123')
    assert col.cpf is None


@pytest.mark.django_db
def test_primeiro_nome_e_derivado_quando_vazio(unidade):
    col = _criar(unidade, nome='Ana Paula Ribeiro')
    assert col.primeiro_nome == 'Ana'


@pytest.mark.django_db
def test_primeiro_nome_informado_e_respeitado(unidade):
    col = _criar(unidade, nome='Ana Paula Ribeiro', primeiro_nome='Paula')
    assert col.primeiro_nome == 'Paula'


# ──────────────────────────────────────────────
# Dedup no nivel do banco
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_varias_pessoas_sem_cpf_convivem(unidade):
    """NULL e distinto de NULL no Postgres, e o dedup depende disso."""
    a = _criar(unidade, nome='Sem Documento Um')
    b = _criar(unidade, nome='Sem Documento Dois')
    assert a.pk != b.pk
    assert a.cpf is None and b.cpf is None


@pytest.mark.django_db
def test_cpf_duplicado_no_mesmo_tenant_e_barrado_pelo_banco(unidade):
    _criar(unidade, nome='Original', cpf='12345678901')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _criar(unidade, nome='Duplicata', cpf='123.456.789-01')


@pytest.mark.django_db
def test_mesmo_cpf_em_tenants_diferentes_e_permitido(unidade):
    """A pessoa pode trabalhar em duas redes distintas. Unicidade e por tenant."""
    outro = Unidade.all_tenants.create(
        tenant=TenantFactory(), nome='Outra Rede', codigo='outra-rede')
    _criar(unidade, nome='Pessoa A', cpf='12345678901')
    col = _criar(outro, nome='Pessoa A', cpf='12345678901')
    assert col.pk


@pytest.mark.django_db
def test_cpf_duplicado_em_unidades_diferentes_do_mesmo_tenant_e_barrado(unidade):
    """
    Unicidade e por tenant, nao por unidade. A pessoa que muda de loja continua
    sendo uma so, e permitir duplicata por unidade recriaria exatamente o
    cadastro paralelo que a regra de fonte unica proibe.
    """
    outra_loja = Unidade.all_tenants.create(
        tenant=unidade.tenant, nome='Loja Norte', codigo='loja-norte')
    _criar(unidade, nome='Pessoa', cpf='12345678901')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _criar(outra_loja, nome='Pessoa', cpf='12345678901')


@pytest.mark.django_db
def test_check_constraint_barra_cpf_vazio_mesmo_por_update_cru(unidade):
    """
    O save() normaliza, mas `queryset.update()` nao passa por ele. Sem esta
    constraint, um '' gravado por atalho faria a proxima insercao sem CPF
    explodir com um IntegrityError incompreensivel, longe da causa.
    """
    col = _criar(unidade)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Colaborador.all_tenants.filter(pk=col.pk).update(cpf='')


@pytest.mark.django_db
def test_check_constraint_barra_cpf_com_formato_errado(unidade):
    col = _criar(unidade)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Colaborador.all_tenants.filter(pk=col.pk).update(cpf='123.456.789')


# ──────────────────────────────────────────────
# Guarda da situacao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_mudar_situacao_por_save_solto_levanta(unidade):
    """A regra central: toda transicao passa por mover_situacao(), porque toda
    transicao precisa gerar historico e telemetria."""
    col = _criar(unidade)
    col = Colaborador.all_tenants.get(pk=col.pk)
    col.situacao = estados.SITUACAO_EM_ADMISSAO
    with pytest.raises(TransicaoNaoAutorizada):
        col.save()


@pytest.mark.django_db
def test_salvar_outros_campos_nao_e_afetado_pela_guarda(unidade):
    col = _criar(unidade)
    col = Colaborador.all_tenants.get(pk=col.pk)
    col.cargo = 'Atendente'
    col.save()
    col.refresh_from_db()
    assert col.cargo == 'Atendente'
    assert col.situacao == estados.SITUACAO_CADASTRO


@pytest.mark.django_db
def test_transicao_autorizada_passa_e_persiste(unidade):
    col = _criar(unidade)
    col = Colaborador.all_tenants.get(pk=col.pk)
    col.situacao = estados.SITUACAO_EM_ADMISSAO
    col._transicao_autorizada = True
    col.save()

    do_banco = Colaborador.all_tenants.get(pk=col.pk)
    assert do_banco.situacao == estados.SITUACAO_EM_ADMISSAO


@pytest.mark.django_db
def test_autorizacao_nao_vaza_pro_save_seguinte(unidade):
    """A flag e consumida a cada save. Se ficasse ligada, o segundo save do
    mesmo objeto passaria calado."""
    col = _criar(unidade)
    col = Colaborador.all_tenants.get(pk=col.pk)
    col.situacao = estados.SITUACAO_EM_ADMISSAO
    col._transicao_autorizada = True
    col.save()

    col.situacao = estados.SITUACAO_EM_EXPERIENCIA
    with pytest.raises(TransicaoNaoAutorizada):
        col.save()


@pytest.mark.django_db
def test_context_manager_desliga_a_guarda_e_persiste(unidade):
    """Escape hatch pra data migration e seed."""
    col = _criar(unidade)
    col = Colaborador.all_tenants.get(pk=col.pk)
    col.situacao = estados.SITUACAO_EM_EXPERIENCIA
    with sem_guarda_de_situacao():
        col.save()

    do_banco = Colaborador.all_tenants.get(pk=col.pk)
    assert do_banco.situacao == estados.SITUACAO_EM_EXPERIENCIA


@pytest.mark.django_db
def test_guarda_volta_a_valer_depois_do_context_manager(unidade):
    col = _criar(unidade)
    col = Colaborador.all_tenants.get(pk=col.pk)
    with sem_guarda_de_situacao():
        col.situacao = estados.SITUACAO_EM_ADMISSAO
        col.save()

    col.situacao = estados.SITUACAO_EM_EXPERIENCIA
    with pytest.raises(TransicaoNaoAutorizada):
        col.save()


@pytest.mark.django_db
def test_guarda_nao_quebra_com_only(unidade):
    """`.only()` traz a instancia sem `situacao`. A guarda precisa se calar em
    vez de comparar com None e acusar transicao que nao houve."""
    col = _criar(unidade)
    parcial = Colaborador.all_tenants.only('nome_completo', 'tenant', 'unidade').get(pk=col.pk)
    parcial.nome_completo = 'Nome Editado'
    parcial.save()

    do_banco = Colaborador.all_tenants.get(pk=col.pk)
    assert do_banco.nome_completo == 'Nome Editado'


@pytest.mark.django_db
def test_refresh_from_db_reancora_a_guarda(unidade):
    """
    Sem reancorar, a instancia em memoria continuaria comparando com a situacao
    antiga e acusaria transicao falsa no proximo save.
    """
    col = _criar(unidade)
    col = Colaborador.all_tenants.get(pk=col.pk)
    Colaborador.all_tenants.filter(pk=col.pk).update(situacao=estados.SITUACAO_EFETIVADO)
    col.refresh_from_db()

    col.cargo = 'Gerente'
    col.save()  # nao pode levantar

    do_banco = Colaborador.all_tenants.get(pk=col.pk)
    assert do_banco.situacao == estados.SITUACAO_EFETIVADO
    assert do_banco.cargo == 'Gerente'


@pytest.mark.django_db
def test_criar_ja_com_situacao_diferente_do_default_e_permitido(unidade):
    """A guarda so vale pra UPDATE. Os tres pontos de entrada precisam poder
    nascer direto em admissao ou experiencia."""
    col = _criar(unidade, situacao=estados.SITUACAO_EM_EXPERIENCIA)
    assert col.pk
    assert col.situacao == estados.SITUACAO_EM_EXPERIENCIA


# ──────────────────────────────────────────────
# Soft delete
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_colaborador_nao_se_apaga(unidade):
    """Apagar destroi historico e a propria possibilidade de readmissao."""
    col = _criar(unidade)
    with pytest.raises(PeopleError):
        col.delete()
    assert Colaborador.all_tenants.filter(pk=col.pk).exists()


@pytest.mark.django_db
def test_remocao_real_exige_flag_explicita(unidade):
    """Existe pro direito ao esquecimento da LGPD, e precisa ser deliberado."""
    col = _criar(unidade)
    col._apagar_de_verdade = True
    col.delete()
    assert not Colaborador.all_tenants.filter(pk=col.pk).exists()


@pytest.mark.django_db
def test_unidade_com_colaborador_nao_pode_ser_apagada(unidade):
    """PROTECT: apagar loja nao pode orfanar pessoa."""
    from django.db.models import ProtectedError
    _criar(unidade)
    with pytest.raises(ProtectedError):
        unidade.delete()


# ──────────────────────────────────────────────
# Consultas de instancia
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_esta_ativo_cobre_as_fases_do_quadro(unidade):
    col = _criar(unidade)
    for situacao in estados.SITUACOES_ATIVAS:
        col.situacao = situacao
        assert col.esta_ativo, f'{situacao} deveria contar como ativo'


@pytest.mark.django_db
def test_desligado_e_freelancer_nao_sao_ativos(unidade):
    """Freelancer e banco de ex colaboradores disponiveis, nao quadro."""
    col = _criar(unidade)
    col.situacao = estados.SITUACAO_DESLIGADO
    assert not col.esta_ativo
    col.situacao = estados.SITUACAO_FREELANCER
    assert not col.esta_ativo


@pytest.mark.django_db
def test_cpf_mascarado_nao_expoe_o_documento(unidade):
    col = _criar(unidade, cpf='12345678901')
    assert '12345678901' not in col.cpf_mascarado
    assert col.cpf_mascarado.endswith('01')


@pytest.mark.django_db
def test_cpf_mascarado_vazio_quando_nao_ha_cpf(unidade):
    col = _criar(unidade)
    assert col.cpf_mascarado == ''


# ──────────────────────────────────────────────
# HistoricoSituacao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_historico_guarda_snapshot_da_transicao(unidade):
    col = _criar(unidade)
    hist = HistoricoSituacao.all_tenants.create(
        tenant=unidade.tenant, colaborador=col,
        de=estados.SITUACAO_CADASTRO, para=estados.SITUACAO_EM_ADMISSAO,
        motivo='Iniciou admissao', dados={'data_admissao': '2026-07-19'},
        origem='painel',
    )
    assert hist.dados['data_admissao'] == '2026-07-19'


@pytest.mark.django_db
def test_historico_some_junto_com_o_colaborador_apagado(unidade):
    """CASCADE aqui e correto: e trilha da pessoa, nao registro independente."""
    col = _criar(unidade)
    HistoricoSituacao.all_tenants.create(
        tenant=unidade.tenant, colaborador=col, de='', para=estados.SITUACAO_CADASTRO)
    col._apagar_de_verdade = True
    col.delete()
    assert not HistoricoSituacao.all_tenants.filter(colaborador_id=col.pk).exists()
