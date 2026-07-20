"""
Formulario publico de candidatura.

O teste mais importante deste arquivo e o de isolamento com o thread local
SUJO DE PROPOSITO. Sem ele nao da pra saber se a view esta protegida ou se
apenas teve sorte, porque numa suite limpa o thread local costuma estar vazio e
o bug de vazamento nao aparece.
"""
import secrets

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.people.models import (
    Cargo, Candidato, ConfiguracaoPeople, LinkCandidatura, Unidade, Vaga,
)
from apps.people.models_recrutamento import JUSTIFICATIVA_AUMENTO
from apps.people.services.candidaturas import MENSAGEM_CONFLITO
from tests.factories import TenantFactory


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   justificativa=JUSTIFICATIVA_AUMENTO)
    vaga.mudar_status('publicada')
    link = LinkCandidatura.all_tenants.create(
        tenant=tenant, vaga=vaga, unidade=unidade, canal='facebook',
        token=secrets.token_urlsafe(32))
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo,
            'vaga': vaga, 'link': link}


@pytest.fixture(autouse=True)
def sem_rate_limit(settings):
    """
    Desliga o rate limit no grosso dos testes.

    Mesmo padrao de tests/test_people_publico.py: todos os testes saem do mesmo
    IP, entao o limite de 5 por minuto derrubaria o sexto POST de QUALQUER
    teste, por engano e nao por defeito. O limite tem teste proprio abaixo, com
    ele religado.
    """
    settings.RATELIMIT_ENABLE = False


def _url(link, acao='formulario'):
    return reverse(f'people_candidatura:{acao}', args=[link.token])


def _payload(**extra):
    dados = {
        'nome_completo': 'Maria de Fátima Oliveira',
        'whatsapp': '(86) 99999-8888',
        'consentimento_lgpd': 'on',
    }
    dados.update(extra)
    return dados


# ── Acesso sem login ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_formulario_abre_sem_login(cenario):
    """
    Se a isencao no middleware faltar, isto redireciona pro login e o QR
    impresso vira papel morto.
    """
    resposta = Client().get(_url(cenario['link']))

    assert resposta.status_code == 200
    assert 'Loja Centro' in resposta.content.decode()


@pytest.mark.django_db
def test_token_invalido_da_404_generico(cenario):
    assert Client().get('/people/candidatura/naoexiste/').status_code == 404


@pytest.mark.django_db
def test_link_desativado_da_404_e_nao_mensagem_propria(cenario):
    """
    Nao diferenciar inexistente de desativado. Diferenciar transformaria a
    pagina em oraculo de enumeracao de tokens.
    """
    cenario['link'].desativar()

    assert Client().get(_url(cenario['link'])).status_code == 404


@pytest.mark.django_db
def test_vaga_pausada_derruba_o_link(cenario):
    cenario['vaga'].mudar_status('pausada')

    assert Client().get(_url(cenario['link'])).status_code == 404


# ── Envio ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_candidatura_cria_o_candidato_com_origem(cenario):
    resposta = Client().post(_url(cenario['link'], 'enviar'), _payload())

    candidato = Candidato.all_tenants.get(tenant=cenario['tenant'])
    assert resposta.status_code == 200
    assert candidato.nome_completo == 'Maria de Fátima Oliveira'
    assert candidato.whatsapp == '86999998888'   # normalizado
    assert candidato.vaga_id == cenario['vaga'].id
    assert candidato.link_origem_id == cenario['link'].id
    assert candidato.unidade_id == cenario['unidade'].id


@pytest.mark.django_db
def test_contador_do_link_incrementa(cenario):
    """E a atribuicao de canal. Sem isso nao da pra saber onde gastar."""
    Client().post(_url(cenario['link'], 'enviar'), _payload())

    cenario['link'].refresh_from_db()
    assert cenario['link'].candidaturas == 1
    assert cenario['link'].ultima_candidatura_em is not None


@pytest.mark.django_db
def test_consentimento_grava_versao_e_ip(cenario):
    """
    Sem a versao, um aceite antigo pareceria valer pro texto novo e a trilha
    nao provaria nada.
    """
    config = ConfiguracaoPeople.get_config(cenario['tenant'])
    config.versao_consentimento_lgpd = '2.1'
    config.save()

    Client().post(_url(cenario['link'], 'enviar'), _payload())

    candidato = Candidato.all_tenants.get(tenant=cenario['tenant'])
    assert candidato.consentimento_lgpd
    assert candidato.consentimento_versao == '2.1'
    assert candidato.consentimento_em is not None


@pytest.mark.django_db
def test_retencao_e_gravada_no_registro(cenario):
    """
    Gravada e nao calculada no expurgo: se o prazo mudar depois, quem se
    candidatou sob a regra antiga tem direito a ela.
    """
    Client().post(_url(cenario['link'], 'enviar'), _payload())

    candidato = Candidato.all_tenants.get(tenant=cenario['tenant'])
    assert candidato.retencao_ate is not None


@pytest.mark.django_db
def test_sem_consentimento_nao_passa(cenario):
    resposta = Client().post(_url(cenario['link'], 'enviar'),
                             _payload(consentimento_lgpd=''))

    assert resposta.status_code == 400
    assert not Candidato.all_tenants.filter(tenant=cenario['tenant']).exists()


@pytest.mark.django_db
def test_whatsapp_curto_demais_e_recusado(cenario):
    resposta = Client().post(_url(cenario['link'], 'enviar'),
                             _payload(whatsapp='123'))

    assert resposta.status_code == 400
    assert not Candidato.all_tenants.filter(tenant=cenario['tenant']).exists()


# ── Dedup por WhatsApp ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_mesmo_whatsapp_nao_cria_segundo_candidato(cenario):
    cliente = Client()
    cliente.post(_url(cenario['link'], 'enviar'), _payload())
    resposta = cliente.post(_url(cenario['link'], 'enviar'),
                            _payload(nome_completo='Outro Nome'))

    assert resposta.status_code == 409
    assert Candidato.all_tenants.filter(tenant=cenario['tenant']).count() == 1


@pytest.mark.django_db
def test_mensagem_de_conflito_nao_vaza_o_candidato_existente(cenario):
    """
    A pagina e publica. Confirmar QUEM esta na base diria "fulano se candidatou
    aqui" pra qualquer um na internet, e o unico dado necessario pra perguntar
    e um numero de telefone.

    O que o visitante digitou VOLTA na resposta de proposito, pra ele nao ter
    que redigitar tudo. Isso nao e vazamento: e o proprio dado dele. O que nao
    pode voltar e o de quem ja estava la.
    """
    cliente = Client()
    cliente.post(_url(cenario['link'], 'enviar'),
                 _payload(nome_completo='Maria de Fátima Oliveira',
                          email='maria.existente@teste.com'))

    # Mesmo numero, dados diferentes: quem submete agora e outra pessoa
    resposta = cliente.post(_url(cenario['link'], 'enviar'),
                            _payload(nome_completo='Joao Curioso',
                                     email='joao@teste.com'))
    corpo = resposta.content.decode()

    assert MENSAGEM_CONFLITO in corpo
    # Nada da primeira candidatura pode aparecer
    assert 'Maria de Fátima' not in corpo
    assert 'maria.existente@teste.com' not in corpo
    # E a mensagem nao pode confirmar nem negar que o numero existe
    assert 'já cadastrado' not in corpo.lower()
    assert 'já existe' not in corpo.lower()


@pytest.mark.django_db
def test_mesmo_numero_em_tenants_diferentes_convive(cenario):
    """A unicidade e POR TENANT: duas redes nao compartilham base."""
    outro = TenantFactory(modulo_people=True)
    outra_unidade = Unidade.all_tenants.create(tenant=outro, nome='Loja Deles',
                                               codigo='deles')
    outro_link = LinkCandidatura.all_tenants.create(
        tenant=outro, vaga=None, unidade=outra_unidade, canal='instagram',
        token=secrets.token_urlsafe(32))

    Client().post(_url(cenario['link'], 'enviar'), _payload())
    Client().post(_url(outro_link, 'enviar'), _payload())

    assert Candidato.all_tenants.filter(whatsapp='86999998888').count() == 2


# ── Anti abuso ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_honeypot_responde_sucesso_falso_e_nao_grava(cenario):
    """
    Sucesso falso pro robo nao aprender qual foi o sinal que o denunciou.
    """
    resposta = Client().post(_url(cenario['link'], 'enviar'),
                             _payload(sobrenome_confirmacao='robo'))

    assert resposta.status_code == 200
    assert 'enviada' in resposta.content.decode().lower()
    assert not Candidato.all_tenants.filter(tenant=cenario['tenant']).exists()


@pytest.mark.django_db
def test_curriculo_grande_demais_e_recusado(cenario):
    grande = SimpleUploadedFile('cv.pdf', b'x' * (6 * 1024 * 1024),
                                content_type='application/pdf')

    resposta = Client().post(_url(cenario['link'], 'enviar'),
                             _payload(curriculo=grande))

    assert resposta.status_code == 400
    assert not Candidato.all_tenants.filter(tenant=cenario['tenant']).exists()


@pytest.mark.django_db
def test_curriculo_de_tipo_errado_e_recusado(cenario):
    executavel = SimpleUploadedFile('cv.exe', b'MZ',
                                    content_type='application/octet-stream')

    resposta = Client().post(_url(cenario['link'], 'enviar'),
                             _payload(curriculo=executavel))

    assert resposta.status_code == 400


@pytest.mark.django_db
def test_rate_limit_por_ip(cenario, settings):
    """
    O unico teste com o limite ligado. Um formulario publico sem ele e convite
    pra enxurrada, e o numero de candidaturas por canal deixaria de significar
    alguma coisa.
    """
    settings.RATELIMIT_ENABLE = True
    cliente = Client()

    respostas = [
        cliente.post(_url(cenario['link'], 'enviar'),
                     _payload(whatsapp=f'8699999{i:04d}'))
        for i in range(7)
    ]

    # block=True levanta Ratelimited, que herda de PermissionDenied: 403.
    assert any(r.status_code == 403 for r in respostas), \
        'rate limit por IP nao disparou'


@pytest.mark.django_db
def test_get_no_endpoint_de_envio_e_recusado(cenario):
    assert Client().get(_url(cenario['link'], 'enviar')).status_code == 405


# ── Isolamento com thread local sujo ─────────────────────────────────────────

@pytest.mark.django_db
def test_nao_vaza_pra_outro_tenant_mesmo_com_thread_local_sujo(cenario):
    """
    O teste que prova que a protecao existe, e nao que teve sorte.

    Numa suite limpa o thread local costuma estar vazio, entao um vazamento
    passaria despercebido. Aqui ele e sujado DE PROPOSITO com outro tenant
    antes da request, simulando gunicorn reusando thread entre requests de
    clientes diferentes.
    """
    from apps.sistema.middleware import set_current_tenant

    intruso = TenantFactory(modulo_people=True)
    Unidade.all_tenants.create(tenant=intruso, nome='Loja do Intruso',
                               codigo='intruso')

    set_current_tenant(intruso)
    try:
        resposta = Client().post(_url(cenario['link'], 'enviar'), _payload())
    finally:
        set_current_tenant(None)

    assert resposta.status_code == 200

    candidato = Candidato.all_tenants.get(whatsapp='86999998888')
    assert candidato.tenant_id == cenario['tenant'].id, (
        'candidato nasceu no tenant errado: o escopo da view publica vazou')
    assert not Candidato.all_tenants.filter(tenant=intruso).exists()


@pytest.mark.django_db
def test_link_de_um_tenant_nao_le_dado_de_outro(cenario):
    outro = TenantFactory(modulo_people=True)
    outra_unidade = Unidade.all_tenants.create(tenant=outro, nome='Loja Secreta',
                                               codigo='secreta')

    corpo = Client().get(_url(cenario['link'])).content.decode()

    assert 'Loja Centro' in corpo
    assert 'Loja Secreta' not in corpo
    assert outra_unidade.nome not in corpo


# ── Anonimizacao (base do expurgo do passo 7) ────────────────────────────────

@pytest.mark.django_db
def test_anonimizar_tira_a_pessoa_e_mantem_a_linha(cenario):
    """
    Se a linha sumisse, o funil de tres meses atras passaria a dizer que
    chegaram menos candidatos do que chegaram.
    """
    Client().post(_url(cenario['link'], 'enviar'), _payload(email='m@teste.com'))
    candidato = Candidato.all_tenants.get(tenant=cenario['tenant'])

    candidato.anonimizar()

    candidato.refresh_from_db()
    assert candidato.whatsapp is None
    assert candidato.email == ''
    assert 'anonimizado' in candidato.nome_completo.lower()
    assert candidato.anonimizado_em is not None
    # A linha e a origem sobrevivem, senao a atribuicao de canal mentiria
    assert candidato.link_origem_id == cenario['link'].id


@pytest.mark.django_db
def test_anonimizar_libera_o_numero_pra_nova_candidatura(cenario):
    """
    Consequencia desejada: quem foi anonimizado pode se candidatar de novo,
    porque a base nao guarda mais nada dele.
    """
    Client().post(_url(cenario['link'], 'enviar'), _payload())
    Candidato.all_tenants.get(tenant=cenario['tenant']).anonimizar()

    resposta = Client().post(_url(cenario['link'], 'enviar'), _payload())

    assert resposta.status_code == 200
    assert Candidato.all_tenants.filter(tenant=cenario['tenant']).count() == 2
