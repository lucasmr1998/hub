"""
Tarefa 217: as duas promessas quebradas do recrutamento.

1. `sla_dias` era campo MORTO. O help_text do model e o helper da tela de fluxo
   diziam "depois disso o candidato aparece como atrasado nesta etapa", e nada
   no modulo calculava atraso. O campo era gravado e nunca lido.

2. Link de banco de talentos NAO ERA CRIAVEL. `LinkCandidatura.vaga` sempre
   aceitou nulo, a view publica tratava o caso e havia testes cobrindo. So nao
   existia botao que criasse um.

O que estes testes defendem: as bordas do atraso (etapa sem prazo nunca marca,
quem saiu do processo nao conta, mover zera o relogio) e o caminho ponta a ponta
do link sem vaga.
"""
import datetime
import secrets

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.people.models import (
    Candidato, Cargo, EtapaPipeline, LinkCandidatura, Unidade, Vaga,
)
from apps.people.services.pipeline import dar_saida, mover_para_etapa
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)   # signal semeia as 6 etapas
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    return {'tenant': tenant, 'unidade': unidade}


def _cliente(cenario, username='rh_217',
             funcionalidades=('people.ver', 'people.gerir_vagas')):
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'],
                                            nome=f'P {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


def _etapa(cenario, nome='Análise de inscrição'):
    return EtapaPipeline.all_tenants.get(tenant=cenario['tenant'], nome=nome)


def _candidato(cenario, etapa=None, dias_atras=0, nome='Alguem'):
    return Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo=nome, etapa=etapa,
        whatsapp=''.join(str(secrets.randbelow(10)) for _ in range(11)),
        etapa_desde=timezone.now() - datetime.timedelta(days=dias_atras))


# ── Atraso: as bordas ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_dentro_do_prazo_nao_marca_atraso(cenario):
    etapa = _etapa(cenario)          # Análise de inscrição, sla_dias=3
    candidato = _candidato(cenario, etapa, dias_atras=2)

    assert candidato.dias_na_etapa == 2
    assert candidato.esta_atrasado is False
    assert candidato.rotulo_atraso == ''


@pytest.mark.django_db
def test_no_limite_do_prazo_ainda_nao_esta_atrasado(cenario):
    """Prazo de 3 dias significa que no terceiro dia ainda esta no prazo."""
    candidato = _candidato(cenario, _etapa(cenario), dias_atras=3)

    assert candidato.esta_atrasado is False


@pytest.mark.django_db
def test_passou_do_prazo_marca_e_conta_os_dias(cenario):
    candidato = _candidato(cenario, _etapa(cenario), dias_atras=5)

    assert candidato.esta_atrasado is True
    assert candidato.dias_de_atraso == 2
    assert candidato.rotulo_atraso == '2 dias atrasado'


@pytest.mark.django_db
def test_um_dia_de_atraso_no_singular(cenario):
    candidato = _candidato(cenario, _etapa(cenario), dias_atras=4)

    assert candidato.rotulo_atraso == '1 dia atrasado'


@pytest.mark.django_db
def test_etapa_sem_prazo_nunca_marca_atraso(cenario):
    """
    Prazo em branco significa "sem prazo", e nao "prazo zero". Sem esta regra,
    toda etapa sem SLA marcaria todo mundo como atrasado no primeiro dia.
    """
    etapa = _etapa(cenario)
    etapa.sla_dias = None
    etapa.save()
    candidato = _candidato(cenario, etapa, dias_atras=90)

    assert candidato.esta_atrasado is False
    assert candidato.dias_na_etapa == 90       # o tempo continua sendo contado


@pytest.mark.django_db
def test_quem_saiu_do_processo_nao_esta_atrasado(cenario):
    """Parado numa saida terminal e o estado final esperado, nao demora."""
    candidato = _candidato(cenario, _etapa(cenario), dias_atras=90)
    dar_saida(candidato, 'banco_talentos', motivo='Sem vaga agora')

    candidato.refresh_from_db()
    assert candidato.esta_atrasado is False
    assert candidato.dias_na_etapa is None


@pytest.mark.django_db
def test_mover_de_etapa_zera_o_relogio(cenario):
    candidato = _candidato(cenario, _etapa(cenario), dias_atras=10)

    mover_para_etapa(candidato, _etapa(cenario, 'Entrevista / Seleção'))

    candidato.refresh_from_db()
    assert candidato.dias_na_etapa == 0
    assert candidato.esta_atrasado is False


@pytest.mark.django_db
def test_editar_o_candidato_nao_zera_o_relogio(cenario):
    """
    A contagem sai de `etapa_desde`, e nao de `atualizado_em`: corrigir um
    telefone nao pode fazer o candidato parecer recem chegado na etapa.
    """
    candidato = _candidato(cenario, _etapa(cenario), dias_atras=10)

    candidato.email = 'novo@exemplo.com'
    candidato.save()

    candidato.refresh_from_db()
    assert candidato.dias_na_etapa == 10


@pytest.mark.django_db
def test_board_mostra_o_atraso(cenario):
    _candidato(cenario, _etapa(cenario), dias_atras=6, nome='Atrasado Silva')

    corpo = _cliente(cenario).get(reverse('people:pipeline_board')).content.decode()

    assert '3 dias atrasado' in corpo


# ── Captacao continua: o link sem vaga ───────────────────────────────────────

@pytest.mark.django_db
def test_cria_link_sem_vaga(cenario):
    _cliente(cenario).post(reverse('people:banco_talentos_link_criar'), {
        'canal': 'instagram', 'unidade': cenario['unidade'].pk,
        'apelido_interno': 'QR do balcão'})

    link = LinkCandidatura.all_tenants.get(tenant=cenario['tenant'])
    assert link.vaga_id is None
    assert link.unidade_id == cenario['unidade'].pk
    assert link.ativo


@pytest.mark.django_db
def test_link_sem_unidade_e_recusado(cenario):
    """
    A unidade e obrigatoria mesmo sem vaga: sem ela o candidato do banco nao
    fica ligado a loja nenhuma e o RH daquela loja nao encontra ele.
    """
    resposta = _cliente(cenario).post(
        reverse('people:banco_talentos_link_criar'),
        {'canal': 'instagram'}, follow=True)

    assert 'unidade' in resposta.content.decode().lower()
    assert not LinkCandidatura.all_tenants.filter(tenant=cenario['tenant']).exists()


@pytest.mark.django_db
def test_candidatura_pelo_link_sem_vaga_chega_sem_vaga(cenario):
    """O caminho que ja existia no backend, agora com porta de entrada."""
    link = LinkCandidatura.all_tenants.create(
        tenant=cenario['tenant'], vaga=None, unidade=cenario['unidade'],
        canal='instagram', token=secrets.token_urlsafe(16))

    Client().post(f'/people/candidatura/{link.token}/enviar/', {
        'nome_completo': 'Livia Prado', 'whatsapp': '86999991234',
        'consentimento_lgpd': 'on'})

    candidato = Candidato.all_tenants.get(nome_completo='Livia Prado')
    assert candidato.vaga_id is None
    assert candidato.link_origem_id == link.pk


@pytest.mark.django_db
def test_a_tela_so_lista_link_sem_vaga(cenario):
    """Link de vaga nao pode vazar pra ca: sao telas com proposito diferente."""
    cargo = Cargo.all_tenants.get(tenant=cenario['tenant'])
    vaga = Vaga.all_tenants.create(tenant=cenario['tenant'],
                                   unidade=cenario['unidade'], cargo=cargo)
    LinkCandidatura.all_tenants.create(
        tenant=cenario['tenant'], vaga=vaga, unidade=cenario['unidade'],
        canal='facebook', apelido_interno='Link da vaga',
        token=secrets.token_urlsafe(16))
    LinkCandidatura.all_tenants.create(
        tenant=cenario['tenant'], vaga=None, unidade=cenario['unidade'],
        canal='instagram', apelido_interno='QR do balcao',
        token=secrets.token_urlsafe(16))

    corpo = _cliente(cenario).get(
        reverse('people:banco_talentos_links')).content.decode()

    assert 'QR do balcao' in corpo
    assert 'Link da vaga' not in corpo


@pytest.mark.django_db
def test_desativar_nao_apaga_o_link(cenario):
    """Apagar destruiria a atribuicao de canal das candidaturas que vieram."""
    link = LinkCandidatura.all_tenants.create(
        tenant=cenario['tenant'], vaga=None, unidade=cenario['unidade'],
        canal='instagram', token=secrets.token_urlsafe(16))

    _cliente(cenario).post(
        reverse('people:banco_talentos_link_alternar', args=[link.pk]))

    link.refresh_from_db()
    assert not link.ativo
    assert LinkCandidatura.all_tenants.filter(pk=link.pk).exists()


@pytest.mark.django_db
def test_quem_so_ve_nao_cria_link(cenario):
    cliente = _cliente(cenario, username='so_ve_217',
                       funcionalidades=('people.ver',))

    assert cliente.get(reverse('people:banco_talentos_links')).status_code == 200
    assert cliente.post(reverse('people:banco_talentos_link_criar'),
                        {'canal': 'instagram'}).status_code == 403
