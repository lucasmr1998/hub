"""
Passo 2 do plano de Recrutamento: Vaga e RequisitoVaga.

As constraints sao exercitadas contra o banco, nao so declaradas. Constraint que
ninguem tenta violar e comentario: passa a suite inteira sem ninguem descobrir
que ela nunca foi criada, ou que foi criada errada.
"""
import pytest
from django.db import IntegrityError, transaction

from apps.people import estados_recrutamento as estados_rs
from apps.people.excecoes import TransicaoInvalida
from apps.people.models_recrutamento import (
    JUSTIFICATIVA_AUMENTO, JUSTIFICATIVA_SUBSTITUICAO,
)


@pytest.fixture
def cenario(db):
    from apps.sistema.models import Tenant
    from apps.people.models import Cargo, Unidade

    tenant = Tenant.objects.create(nome='Rede Vaga', slug='rede-vaga',
                                   modulo_people=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo}


def _vaga(cenario, **kwargs):
    from apps.people.models import Vaga

    dados = {
        'tenant': cenario['tenant'],
        'unidade': cenario['unidade'],
        'cargo': cenario['cargo'],
        'justificativa': JUSTIFICATIVA_AUMENTO,
    }
    dados.update(kwargs)
    return Vaga.all_tenants.create(**dados)


# ── Maquina de status da vaga (pura) ─────────────────────────────────────────

def test_rascunho_publica_e_encerra():
    estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_RASCUNHO,
                                      estados_rs.STATUS_VAGA_PUBLICADA)
    estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_PUBLICADA,
                                      estados_rs.STATUS_VAGA_ENCERRADA)


def test_publicada_pausa_e_volta():
    """Pausar e o caso real de 'temos candidato demais, segura um pouco'."""
    estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_PUBLICADA,
                                      estados_rs.STATUS_VAGA_PAUSADA)
    estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_PAUSADA,
                                      estados_rs.STATUS_VAGA_PUBLICADA)


def test_encerrada_nao_reabre_e_a_mensagem_ensina_o_caminho():
    """
    Reabrir juntaria duas janelas de captacao no mesmo funil, e o relatorio
    somaria periodos diferentes como se fossem um.
    """
    with pytest.raises(TransicaoInvalida) as erro:
        estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_ENCERRADA,
                                          estados_rs.STATUS_VAGA_PUBLICADA)
    assert 'vaga nova' in str(erro.value).lower()


def test_pausada_nao_pula_direto_pra_rascunho():
    with pytest.raises(TransicaoInvalida):
        estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_PAUSADA,
                                          estados_rs.STATUS_VAGA_RASCUNHO)


def test_status_desconhecido_e_recusado():
    with pytest.raises(TransicaoInvalida):
        estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_RASCUNHO,
                                          'aprovada')


# ── Vaga ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_vaga_nasce_em_rascunho(cenario):
    vaga = _vaga(cenario)

    assert vaga.status == estados_rs.STATUS_VAGA_RASCUNHO
    assert vaga.publicada_em is None
    assert not vaga.aceita_candidatura


@pytest.mark.django_db
def test_limite_de_aprovados_default_e_50(cenario):
    """Default da spec de origem, com minimo 1."""
    assert _vaga(cenario).limite_aprovados == 50


@pytest.mark.django_db
def test_o_banco_recusa_limite_de_aprovados_zero(cenario):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _vaga(cenario, limite_aprovados=0)


@pytest.mark.django_db
def test_nome_exibido_cai_no_cargo_quando_nao_ha_titulo(cenario):
    assert _vaga(cenario).nome_exibido == 'Atendente'
    assert _vaga(cenario, titulo='Atendente noturno').nome_exibido == 'Atendente noturno'


@pytest.mark.django_db
def test_publicar_carimba_a_data_e_passa_a_aceitar_candidatura(cenario):
    vaga = _vaga(cenario)

    vaga.mudar_status(estados_rs.STATUS_VAGA_PUBLICADA)

    assert vaga.aceita_candidatura
    assert vaga.publicada_em is not None


@pytest.mark.django_db
def test_republicar_depois_de_pausar_nao_reescreve_a_data_original(cenario):
    """
    Se reescrevesse, o tempo de captacao encolheria sozinho no relatorio a cada
    pausa, e a vaga pareceria mais eficiente do que foi.
    """
    vaga = _vaga(cenario)
    vaga.mudar_status(estados_rs.STATUS_VAGA_PUBLICADA)
    primeira_publicacao = vaga.publicada_em

    vaga.mudar_status(estados_rs.STATUS_VAGA_PAUSADA)
    vaga.mudar_status(estados_rs.STATUS_VAGA_PUBLICADA)

    assert vaga.publicada_em == primeira_publicacao


@pytest.mark.django_db
def test_vaga_pausada_nao_aceita_candidatura(cenario):
    vaga = _vaga(cenario)
    vaga.mudar_status(estados_rs.STATUS_VAGA_PUBLICADA)
    vaga.mudar_status(estados_rs.STATUS_VAGA_PAUSADA)

    assert not vaga.aceita_candidatura


@pytest.mark.django_db
def test_encerrar_carimba_a_data(cenario):
    vaga = _vaga(cenario)
    vaga.mudar_status(estados_rs.STATUS_VAGA_ENCERRADA)

    assert vaga.encerrada_em is not None
    assert not vaga.aceita_candidatura


@pytest.mark.django_db
def test_mudar_status_invalido_levanta_e_nao_grava(cenario):
    vaga = _vaga(cenario)
    vaga.mudar_status(estados_rs.STATUS_VAGA_ENCERRADA)

    with pytest.raises(TransicaoInvalida):
        vaga.mudar_status(estados_rs.STATUS_VAGA_PUBLICADA)

    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_ENCERRADA


# ── A regra do substituido ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_substituicao_aceita_colaborador_substituido(cenario):
    from apps.people.models import Colaborador

    pessoa = Colaborador.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Quem Vai Sair')

    vaga = _vaga(cenario, justificativa=JUSTIFICATIVA_SUBSTITUICAO,
                 colaborador_substituido=pessoa)

    assert vaga.colaborador_substituido_id == pessoa.id


@pytest.mark.django_db
def test_o_banco_recusa_substituido_sem_justificativa_de_substituicao(cenario):
    """
    Sem esta constraint, trocar a justificativa depois deixaria pendurada a
    referencia a alguem que ninguem esta substituindo, e o alerta de pendencia
    no DP passaria a apontar pro nada.
    """
    from apps.people.models import Colaborador

    pessoa = Colaborador.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Nao Vai Sair')

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _vaga(cenario, justificativa=JUSTIFICATIVA_AUMENTO,
                  colaborador_substituido=pessoa)


@pytest.mark.django_db
def test_aumento_de_quadro_sem_substituido_passa(cenario):
    assert _vaga(cenario).colaborador_substituido_id is None


# ── RequisitoVaga: os dois usos separados ────────────────────────────────────

@pytest.mark.django_db
def test_requisito_pode_publicar_e_filtrar_ao_mesmo_tempo(cenario):
    """
    O caso do meio, que e o mais comum, e que um enum de tres valores destruiria.
    """
    from apps.people.models import RequisitoVaga

    vaga = _vaga(cenario)
    req = RequisitoVaga.all_tenants.create(
        tenant=cenario['tenant'], vaga=vaga,
        texto='Disponibilidade aos domingos',
        aparece_no_anuncio=True, usar_na_triagem=True)

    assert req in vaga.requisitos_do_anuncio()
    assert req in vaga.requisitos_de_triagem()


@pytest.mark.django_db
def test_requisito_pode_filtrar_sem_aparecer_no_anuncio(cenario):
    """
    E o mecanismo que a spec descreve: filtrar por coisa que nao convem
    publicar, tipo experiencia minima, pra nao afastar quem se candidataria.
    """
    from apps.people.models import RequisitoVaga

    vaga = _vaga(cenario)
    req = RequisitoVaga.all_tenants.create(
        tenant=cenario['tenant'], vaga=vaga,
        texto='Experiência mínima de 6 meses',
        aparece_no_anuncio=False, usar_na_triagem=True)

    assert req not in vaga.requisitos_do_anuncio()
    assert req in vaga.requisitos_de_triagem()


@pytest.mark.django_db
def test_o_banco_recusa_requisito_que_nao_publica_nem_filtra(cenario):
    """Dado morto: o usuario digitou achando que servia pra alguma coisa."""
    from apps.people.models import RequisitoVaga

    vaga = _vaga(cenario)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RequisitoVaga.all_tenants.create(
                tenant=cenario['tenant'], vaga=vaga, texto='Nada',
                aparece_no_anuncio=False, usar_na_triagem=False)


@pytest.mark.django_db
def test_requisitos_saem_na_ordem(cenario):
    from apps.people.models import RequisitoVaga

    vaga = _vaga(cenario)
    for ordem, texto in [(2, 'Segundo'), (1, 'Primeiro'), (3, 'Terceiro')]:
        RequisitoVaga.all_tenants.create(tenant=cenario['tenant'], vaga=vaga,
                                         texto=texto, ordem=ordem)

    assert [r.texto for r in vaga.requisitos.all()] == ['Primeiro', 'Segundo',
                                                        'Terceiro']


@pytest.mark.django_db
def test_apagar_vaga_leva_os_requisitos_junto(cenario):
    from apps.people.models import RequisitoVaga

    vaga = _vaga(cenario)
    RequisitoVaga.all_tenants.create(tenant=cenario['tenant'], vaga=vaga,
                                     texto='Some junto')
    vaga.delete()

    assert not RequisitoVaga.all_tenants.filter(texto='Some junto').exists()


# ── Multi tenancy ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_vaga_nao_vaza_entre_tenants(cenario):
    from apps.sistema.models import Tenant
    from apps.people.models import Cargo, Unidade, Vaga

    outro = Tenant.objects.create(nome='Outra Rede', slug='outra-rede-vaga',
                                  modulo_people=True)
    outra_unidade = Unidade.all_tenants.create(tenant=outro, nome='Loja Deles',
                                               codigo='deles')
    outro_cargo = Cargo.all_tenants.create(tenant=outro, nome='Atendente')

    _vaga(cenario)
    Vaga.all_tenants.create(tenant=outro, unidade=outra_unidade,
                            cargo=outro_cargo,
                            justificativa=JUSTIFICATIVA_AUMENTO)

    do_primeiro = Vaga.all_tenants.filter(tenant=cenario['tenant'])

    assert do_primeiro.count() == 1
    assert do_primeiro.first().unidade.nome == 'Loja Centro'


@pytest.mark.django_db
def test_cargo_com_vaga_nao_pode_ser_apagado(cenario):
    """
    PROTECT de proposito: apagar o cargo deixaria a vaga sem a informacao
    central dela, e o historico de contratacao perderia o eixo de agregacao.
    """
    from django.db.models import ProtectedError

    _vaga(cenario)

    with pytest.raises(ProtectedError):
        cenario['cargo'].delete()
