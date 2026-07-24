"""
Requisicao de vaga com aprovacao (gap 16).

O QUE ESTES TESTES DEFENDEM, em ordem de gravidade:

1. VAGA AGUARDANDO OU REJEITADA NAO RECEBE CANDIDATURA. Requisicao que ainda nao
   foi aprovada nao pode estar captando gente pela porta dos fundos.
2. REJEICAO EXIGE MOTIVO. Sem motivo, o gestor reenvia o mesmo erro e o fluxo so
   adicionou atrito.
3. SUBSTITUICAO EXIGE APONTAR QUEM SAIU. E o que liga a vaga ao Quadro; sem
   isso, "substituicao" vira rotulo sem consequencia.
4. A DECISAO NAO SE ACUMULA. Reenviar limpa o carimbo da decisao anterior, senao
   a tela diz "rejeitada por Fulano" numa vaga que esta na fila.
"""
import pytest

from apps.people import estados_recrutamento as estados_rs
from apps.people.excecoes import TransicaoInvalida
from apps.people.models_recrutamento import (
    JUSTIFICATIVA_AUMENTO, JUSTIFICATIVA_SUBSTITUICAO,
)
from apps.people.services.vagas import (
    RequisicaoInvalida, aprovar, rejeitar, solicitar,
)


@pytest.fixture
def cenario(db):
    from django.contrib.auth.models import User

    from apps.people.models import Cargo, Unidade
    from apps.sistema.models import Tenant

    tenant = Tenant.objects.create(nome='Rede Req', slug='rede-req',
                                   modulo_people=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    rh = User.objects.create_user('rh_req', 'rh@req.local', 'x')
    gestor = User.objects.create_user('gestor_req', 'gestor@req.local', 'x')
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo,
            'rh': rh, 'gestor': gestor}


def _requisicao(cenario, **kwargs):
    from apps.people.models import Vaga

    dados = {
        'tenant': cenario['tenant'],
        'unidade': cenario['unidade'],
        'cargo': cenario['cargo'],
        'justificativa': JUSTIFICATIVA_AUMENTO,
        'status': estados_rs.STATUS_VAGA_AGUARDANDO,
        'criada_por': cenario['gestor'],
    }
    dados.update(kwargs)
    return Vaga.all_tenants.create(**dados)


# ── A garantia central: requisicao nao capta ─────────────────────────────────

def test_aguardando_e_rejeitada_nao_recebem_candidatura():
    """
    O TESTE MAIS IMPORTANTE DESTE ARQUIVO.

    Se um destes entrasse em STATUS_VAGA_ACEITA_CANDIDATURA, uma requisicao nao
    aprovada estaria captando candidato pela porta dos fundos, e o fluxo de
    aprovacao viraria enfeite.
    """
    aceita = estados_rs.STATUS_VAGA_ACEITA_CANDIDATURA
    assert estados_rs.STATUS_VAGA_AGUARDANDO not in aceita
    assert estados_rs.STATUS_VAGA_REJEITADA not in aceita
    assert aceita == (estados_rs.STATUS_VAGA_PUBLICADA,)
    # E o atalho que board e filtros usam pra nao enumerar status na consulta.
    assert set(estados_rs.STATUS_VAGA_PRE_PROCESSO) == {
        estados_rs.STATUS_VAGA_AGUARDANDO, estados_rs.STATUS_VAGA_REJEITADA}


# ── Maquina de estados (pura) ────────────────────────────────────────────────

def test_aprovar_leva_pra_rascunho_e_nao_pro_ar():
    """Decisao 1: o RH aprova o PEDIDO, depois arruma o ANUNCIO."""
    estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_AGUARDANDO,
                                      estados_rs.STATUS_VAGA_RASCUNHO)
    with pytest.raises(TransicaoInvalida):
        estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_AGUARDANDO,
                                          estados_rs.STATUS_VAGA_PUBLICADA)


def test_rejeitada_volta_pra_fila():
    """Sem esta aresta, corrigir exigiria abrir outra vaga e o motivo se perde."""
    estados_rs.validar_transicao_vaga(estados_rs.STATUS_VAGA_REJEITADA,
                                      estados_rs.STATUS_VAGA_AGUARDANDO)


# ── Servico ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_aprovar_carimba_quem_decidiu_e_manda_pra_rascunho(cenario):
    vaga = _requisicao(cenario)

    aprovar(vaga, usuario=cenario['rh'])

    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_RASCUNHO
    assert vaga.aprovada_por_id == cenario['rh'].pk
    assert vaga.decidida_em is not None
    # Nao foi ao ar: publicar continua sendo um passo separado do RH.
    assert vaga.publicada_em is None


@pytest.mark.django_db
def test_rejeitar_sem_motivo_e_recusado(cenario):
    """O motivo e o que o gestor le pra corrigir. Sem ele, o fluxo so atrapalha."""
    vaga = _requisicao(cenario)

    with pytest.raises(RequisicaoInvalida):
        rejeitar(vaga, usuario=cenario['rh'], motivo='   ')

    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_AGUARDANDO


@pytest.mark.django_db
def test_rejeitar_guarda_o_motivo(cenario):
    vaga = _requisicao(cenario)

    rejeitar(vaga, usuario=cenario['rh'], motivo='Quadro já está completo.')

    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_REJEITADA
    assert vaga.motivo_rejeicao == 'Quadro já está completo.'
    assert vaga.aprovada_por_id == cenario['rh'].pk


@pytest.mark.django_db
def test_reenviar_limpa_a_decisao_anterior(cenario):
    """
    Requisicao reenviada espera decisao NOVA. Deixar o carimbo velho faria a
    tela dizer "rejeitada por Fulano" numa vaga que esta na fila.
    """
    vaga = _requisicao(cenario)
    rejeitar(vaga, usuario=cenario['rh'], motivo='Faltou justificar o turno.')

    solicitar(vaga, usuario=cenario['gestor'])

    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_AGUARDANDO
    assert vaga.aprovada_por_id is None
    assert vaga.decidida_em is None


@pytest.mark.django_db
def test_aprovar_limpa_motivo_de_rejeicao_antiga(cenario):
    """Vaga aprovada exibindo o texto da recusa anterior confunde quem le."""
    vaga = _requisicao(cenario)
    rejeitar(vaga, usuario=cenario['rh'], motivo='Sem verba neste mes.')
    solicitar(vaga, usuario=cenario['gestor'])

    aprovar(vaga, usuario=cenario['rh'])

    vaga.refresh_from_db()
    assert vaga.motivo_rejeicao == ''


@pytest.mark.django_db
def test_substituicao_exige_apontar_quem_saiu(cenario):
    """E o que liga a vaga ao Quadro da unidade."""
    from apps.people.models import Vaga

    vaga = Vaga.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], status=estados_rs.STATUS_VAGA_REJEITADA,
        justificativa=JUSTIFICATIVA_SUBSTITUICAO)

    with pytest.raises(RequisicaoInvalida):
        solicitar(vaga, usuario=cenario['gestor'])


@pytest.mark.django_db
def test_sem_justificativa_nao_entra_na_fila(cenario):
    """A justificativa e o ponto da requisicao."""
    from apps.people.models import Vaga

    vaga = Vaga.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], status=estados_rs.STATUS_VAGA_REJEITADA,
        justificativa='')

    with pytest.raises(RequisicaoInvalida):
        solicitar(vaga, usuario=cenario['gestor'])


@pytest.mark.django_db
def test_nao_decide_vaga_que_nao_esta_na_fila(cenario):
    """Aprovar vaga ja publicada seria decisao fora de ordem."""
    vaga = _requisicao(cenario, status=estados_rs.STATUS_VAGA_RASCUNHO)

    with pytest.raises(RequisicaoInvalida):
        aprovar(vaga, usuario=cenario['rh'])
    with pytest.raises(RequisicaoInvalida):
        rejeitar(vaga, usuario=cenario['rh'], motivo='qualquer')


def test_solicitar_vaga_e_funcionalidade_separada_de_gerir():
    """
    Quem solicita nao aprova. Sem essa separacao o fluxo vira burocracia
    decorativa, com o mesmo usuario nos dois lados.
    """
    from apps.people.management.commands.seed_people_funcionalidades import (
        FUNCIONALIDADES, PERFIL_DEFAULTS,
    )

    codigos = [f['codigo'] for f in FUNCIONALIDADES]
    assert 'people.solicitar_vaga' in codigos

    gestor = PERFIL_DEFAULTS['Gestor']
    assert 'people.solicitar_vaga' in gestor
    assert 'people.gerir_vagas' not in gestor


# ── Views e permissao ────────────────────────────────────────────────────────
#
# A separacao de quem pede e quem decide e o ponto do fluxo. Se qualquer um dos
# testes abaixo cair, a governanca virou enfeite: o mesmo usuario estaria nos
# dois lados.

def _cliente(cenario, username, funcionalidades):
    from django.contrib.auth.models import User
    from django.test import Client

    from apps.sistema.models import (
        ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
        PermissaoUsuario,
    )

    ConfiguracaoEmpresa.all_tenants.get_or_create(
        tenant=cenario['tenant'],
        defaults={'nome_empresa': cenario['tenant'].nome, 'ativo': True})

    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'],
                                            nome=f'Perfil {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo,
            defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'],
                                    perfil=perfil)
    cliente = Client()
    cliente.force_login(user)
    return cliente


def _gestor(cenario):
    """Pede, mas nao decide."""
    return _cliente(cenario, 'gestor_view',
                    ['people.ver', 'people.solicitar_vaga'])


def _rh(cenario):
    """Decide."""
    return _cliente(cenario, 'rh_view', ['people.ver', 'people.gerir_vagas'])


@pytest.mark.django_db
def test_gestor_solicita_e_a_vaga_entra_na_fila(cenario):
    from django.urls import reverse

    from apps.people.models import Vaga

    resposta = _gestor(cenario).post(reverse('people:vaga_solicitar'), {
        'unidade': cenario['unidade'].pk,
        'cargo': cenario['cargo'].pk,
        'justificativa': JUSTIFICATIVA_AUMENTO,
        'observacoes': 'Loja sem cobertura no turno da noite.',
    })

    assert resposta.status_code == 302
    vaga = Vaga.all_tenants.get(tenant=cenario['tenant'])
    assert vaga.status == estados_rs.STATUS_VAGA_AGUARDANDO
    # `criada_por` E o solicitante: e o registro de quem pediu.
    assert vaga.criada_por.username == 'gestor_view'


@pytest.mark.django_db
def test_quem_so_solicita_nao_aprova(cenario):
    """
    O TESTE QUE SUSTENTA A GOVERNANCA.

    Se o gestor conseguisse aprovar, ele estaria carimbando o proprio pedido e
    o fluxo inteiro seria teatro.
    """
    from django.urls import reverse

    vaga = _requisicao(cenario)

    resposta = _gestor(cenario).post(
        reverse('people:vaga_aprovar', args=[vaga.pk]))

    assert resposta.status_code in (302, 403)
    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_AGUARDANDO


@pytest.mark.django_db
def test_rh_aprova_e_a_vaga_vai_pra_rascunho(cenario):
    from django.urls import reverse

    vaga = _requisicao(cenario)

    resposta = _rh(cenario).post(reverse('people:vaga_aprovar', args=[vaga.pk]))

    assert resposta.status_code == 302
    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_RASCUNHO
    assert vaga.publicada_em is None   # aprovar nao publica


@pytest.mark.django_db
def test_rh_rejeita_com_motivo_e_o_gestor_reenvia(cenario):
    """O ciclo completo da recusa: rejeita, o gestor ve o motivo e reenvia."""
    from django.urls import reverse

    vaga = _requisicao(cenario)

    _rh(cenario).post(reverse('people:vaga_rejeitar', args=[vaga.pk]),
                      {'motivo': 'Quadro completo neste turno.'})
    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_REJEITADA
    assert 'Quadro completo' in vaga.motivo_rejeicao

    _gestor(cenario).post(reverse('people:vaga_reenviar', args=[vaga.pk]))
    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_AGUARDANDO


@pytest.mark.django_db
def test_lista_de_vagas_renderiza_com_a_fila(cenario):
    """
    Render de verdade: template com erro de sintaxe ou componente recebendo
    formato errado passa no `check` e so aparece quando alguem abre a pagina.
    """
    from django.urls import reverse

    _requisicao(cenario)
    corpo = _rh(cenario).get(reverse('people:vagas_lista')).content.decode()

    assert 'aguardando sua aprova' in corpo         # aviso da fila
    assert 'id="modal-rejeitar"' in corpo
    # A DIV, e nao a string solta: o JS cita o id em `abrirModal('modal-...')`
    # mesmo quando o botao nao existe, e isso e inofensivo.
    assert 'id="modal-solicitar"' not in corpo      # RH puro nao solicita


@pytest.mark.django_db
def test_gestor_ve_o_modal_de_solicitar(cenario):
    from django.urls import reverse

    corpo = _gestor(cenario).get(reverse('people:vagas_lista')).content.decode()

    assert 'id="modal-solicitar"' in corpo
    assert 'id="modal-rejeitar"' not in corpo       # nao decide, nao ve
