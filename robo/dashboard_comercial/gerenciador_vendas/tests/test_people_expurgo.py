"""
Expurgo LGPD do banco de talentos (passo 7).

Materializa a decisao D3: prazo declarado, expurgo automatico, anonimizar em vez
de deletar. O teste que mais importa e o de que o candidato dentro do prazo NAO
e tocado: um expurgo agressivo demais apaga dado que ainda podia ser usado, e e
tao ruim quanto nao expurgar.
"""
import secrets
from datetime import timedelta
from io import StringIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from apps.people.models import Cargo, Candidato, Unidade, Vaga
from apps.people.models_recrutamento import JUSTIFICATIVA_AUMENTO
from tests.factories import TenantFactory


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   justificativa=JUSTIFICATIVA_AUMENTO)
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo, 'vaga': vaga}


def _candidato(cenario, *, retencao_ate=None, **kwargs):
    dados = {
        'tenant': cenario['tenant'], 'unidade': cenario['unidade'],
        'vaga': cenario['vaga'], 'nome_completo': 'Fulano de Tal',
        'whatsapp': ''.join(str(secrets.randbelow(10)) for _ in range(11)),
        'email': 'fulano@teste.com', 'retencao_ate': retencao_ate,
    }
    dados.update(kwargs)
    return Candidato.all_tenants.create(**dados)


def _rodar(dry=False):
    saida = StringIO()
    args = ['--dry-run'] if dry else []
    call_command('expurgar_candidatos', *args, stdout=saida)
    return saida.getvalue()


# ── O que expurga e o que nao ────────────────────────────────────────────────

@pytest.mark.django_db
def test_candidato_com_retencao_vencida_e_anonimizado(cenario):
    ontem = timezone.localdate() - timedelta(days=1)
    candidato = _candidato(cenario, retencao_ate=ontem)

    _rodar()

    candidato.refresh_from_db()
    assert candidato.anonimizado_em is not None
    assert candidato.whatsapp is None
    assert candidato.email == ''
    assert 'anonimizado' in candidato.nome_completo.lower()


@pytest.mark.django_db
def test_candidato_dentro_do_prazo_nao_e_tocado(cenario):
    """
    O teste que segura o expurgo agressivo. Apagar dado que ainda vale e tao
    ruim quanto nao apagar o que venceu.
    """
    amanha = timezone.localdate() + timedelta(days=1)
    candidato = _candidato(cenario, retencao_ate=amanha)

    _rodar()

    candidato.refresh_from_db()
    assert candidato.anonimizado_em is None
    assert candidato.whatsapp is not None
    assert candidato.email == 'fulano@teste.com'


@pytest.mark.django_db
def test_candidato_sem_prazo_nunca_expurga(cenario):
    """retencao_ate nulo = retencao desligada pro tenant. Nao entra na fila."""
    candidato = _candidato(cenario, retencao_ate=None)

    _rodar()

    candidato.refresh_from_db()
    assert candidato.anonimizado_em is None


@pytest.mark.django_db
def test_vencido_hoje_ainda_nao_expurga(cenario):
    """
    Vence HOJE quer dizer que hoje ainda pode. O filtro e retencao_ate < hoje,
    entao o corte e no dia seguinte. Detalhe que evita apagar um dia cedo
    demais.
    """
    hoje = timezone.localdate()
    candidato = _candidato(cenario, retencao_ate=hoje)

    _rodar()

    candidato.refresh_from_db()
    assert candidato.anonimizado_em is None


# ── Curriculo ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_expurgo_apaga_o_arquivo_do_curriculo(cenario):
    """
    O curriculo e o dado mais sensivel, e nao entra em agregacao nenhuma: some
    de verdade, nao so anonimiza a linha.
    """
    ontem = timezone.localdate() - timedelta(days=1)
    cv = SimpleUploadedFile('cv.pdf', b'conteudo do curriculo',
                            content_type='application/pdf')
    candidato = _candidato(cenario, retencao_ate=ontem, curriculo=cv)
    caminho = candidato.curriculo.path

    import os
    assert os.path.exists(caminho)

    _rodar()

    candidato.refresh_from_db()
    assert not candidato.curriculo
    assert not os.path.exists(caminho)


# ── A linha e a origem sobrevivem ────────────────────────────────────────────

@pytest.mark.django_db
def test_a_linha_e_a_origem_sobrevivem_pro_funil(cenario):
    """
    Se a linha sumisse, o funil de tres meses atras diria que chegaram menos
    candidatos do que chegaram. A pessoa some, o registro fica.
    """
    ontem = timezone.localdate() - timedelta(days=1)
    candidato = _candidato(cenario, retencao_ate=ontem)
    candidato_id = candidato.pk
    vaga_id = candidato.vaga_id

    _rodar()

    sobrevivente = Candidato.all_tenants.get(pk=candidato_id)
    assert sobrevivente.vaga_id == vaga_id
    assert sobrevivente.criado_em is not None


# ── Idempotencia e dry-run ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_rodar_de_novo_nao_reprocessa(cenario):
    ontem = timezone.localdate() - timedelta(days=1)
    candidato = _candidato(cenario, retencao_ate=ontem)

    _rodar()
    momento = Candidato.all_tenants.get(pk=candidato.pk).anonimizado_em

    _rodar()  # segunda vez
    depois = Candidato.all_tenants.get(pk=candidato.pk).anonimizado_em

    assert momento == depois   # nao reprocessou


@pytest.mark.django_db
def test_dry_run_conta_mas_nao_anonimiza(cenario):
    ontem = timezone.localdate() - timedelta(days=1)
    candidato = _candidato(cenario, retencao_ate=ontem)

    saida = _rodar(dry=True)

    candidato.refresh_from_db()
    assert candidato.anonimizado_em is None
    assert '1' in saida


@pytest.mark.django_db
def test_expurgo_atravessa_tenants(cenario):
    """
    Obrigacao legal vale pra todos os tenants de uma vez, sem request pra dar
    escopo. Por isso o comando usa all_tenants.
    """
    outro = TenantFactory(modulo_people=True)
    outra_unidade = Unidade.all_tenants.create(tenant=outro, nome='Deles',
                                               codigo='deles')
    ontem = timezone.localdate() - timedelta(days=1)

    do_primeiro = _candidato(cenario, retencao_ate=ontem)
    do_outro = Candidato.all_tenants.create(
        tenant=outro, unidade=outra_unidade, nome_completo='Do Outro',
        whatsapp='55119' + str(secrets.randbelow(1000000)).zfill(6),
        retencao_ate=ontem)

    _rodar()

    do_primeiro.refresh_from_db()
    do_outro.refresh_from_db()
    assert do_primeiro.anonimizado_em is not None
    assert do_outro.anonimizado_em is not None
