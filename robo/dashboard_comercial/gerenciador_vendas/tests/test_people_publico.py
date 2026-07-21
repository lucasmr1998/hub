"""
Testes do formulario publico de auto cadastro.

E a superficie mais exposta do modulo: URL aberta na internet, sem usuario
logado, e a unica coisa que diz de qual empresa e o cadastro e um token. Os
testes aqui existem em tres frentes, todas com modo de falha silencioso:

1. ISOLAMENTO. Sem usuario, o TenantManager nao filtra nada e o TenantMixin nao
   preenche tenant. Um erro aqui grava a pessoa na empresa errada.
2. VAZAMENTO DE INFORMACAO. A resposta de conflito nao pode dizer que o CPF ja
   existe, senao a pagina vira um oraculo de "fulano trabalha aqui?".
3. ABUSO. Link publico sem teto vira porta pra robo encher o board.
"""
import pytest
from datetime import timedelta

from django.test import Client
from django.utils import timezone

from apps.people import estados
from apps.people.campos_formulario import config_padrao
from apps.people.models import (
    Colaborador, LinkCadastroUnidade, SubmissaoLinkCadastro, TemplateFormulario, Unidade,
)
from apps.people.services import criar_link, desativar_link, mover_situacao, registrar_colaborador
from apps.sistema.models import ConfiguracaoEmpresa
from apps.people.utils import NOME_HONEYPOT
from tests.factories import TenantFactory


CPF_VALIDO = '52998224725'
CPF_VALIDO_2 = '15350946056'


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant, nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro', codigo='loja-centro')
    link = criar_link(unidade)
    return {'tenant': tenant, 'unidade': unidade, 'link': link}


@pytest.fixture(autouse=True)
def sem_rate_limit(settings):
    """
    Desliga o rate limit no grosso dos testes. Ele tem teste proprio, e deixado
    ligado aqui faria o quinto cadastro de qualquer teste falhar por engano.
    """
    settings.RATELIMIT_ENABLE = False


def _url(link):
    return f'/people/publico/{link.token}/'


def _enviar(cliente, link, **campos):
    dados = {'consentimento_lgpd': 'on'}
    dados.update(campos)
    return cliente.post(f'/people/publico/{link.token}/enviar/', dados)


# ──────────────────────────────────────────────
# A pagina abre sem login
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_formulario_abre_sem_autenticacao(cenario):
    """
    Se o LoginRequiredMiddleware nao estiver isento, isto vira 302 pro login e o
    colaborador na porta da loja nao consegue se cadastrar.
    """
    resposta = Client().get(_url(cenario['link']))
    assert resposta.status_code == 200


@pytest.mark.django_db
def test_formulario_nao_e_barrado_pelo_middleware_de_permissao(cenario):
    """
    O _MODULO_MAP casa '/people/' por SUBSTRING. Sem a isencao em
    _PERM_SKIP_PATHS, a rota publica levaria 403 do gate do modulo.
    """
    resposta = Client().get(_url(cenario['link']))
    assert resposta.status_code != 403


@pytest.mark.django_db
def test_pagina_mostra_a_loja(cenario):
    corpo = Client().get(_url(cenario['link'])).content.decode()
    assert 'Loja Centro' in corpo


@pytest.mark.django_db
def test_token_invalido_da_404(cenario):
    assert Client().get('/people/publico/nao-existe/').status_code == 404


@pytest.mark.django_db
def test_link_desativado_da_404(cenario):
    desativar_link(cenario['link'])
    assert Client().get(_url(cenario['link'])).status_code == 404


@pytest.mark.django_db
def test_link_expirado_da_404(cenario):
    cenario['link'].expira_em = timezone.now() - timedelta(minutes=1)
    cenario['link'].save()
    assert Client().get(_url(cenario['link'])).status_code == 404


@pytest.mark.django_db
def test_unidade_inativa_da_404(cenario):
    """Loja fechada nao deve continuar recebendo cadastro."""
    cenario['unidade'].ativo = False
    cenario['unidade'].save()
    assert Client().get(_url(cenario['link'])).status_code == 404


@pytest.mark.django_db
def test_todos_os_404_sao_iguais(cenario):
    """
    Token invalido, expirado e desativado precisam ser indistinguiveis. Mensagem
    diferente vira oraculo de quais tokens ja existiram.
    """
    inexistente = Client().get('/people/publico/nao-existe/')
    desativar_link(cenario['link'])
    desativado = Client().get(_url(cenario['link']))
    assert inexistente.status_code == desativado.status_code == 404


# ──────────────────────────────────────────────
# Cadastro
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cadastro_cria_no_tenant_do_link(cenario):
    """
    O nucleo do isolamento. Sem usuario logado, o unico caminho pro tenant e o
    token, e errar aqui grava a pessoa na empresa errada.
    """
    _enviar(Client(), cenario['link'],
            nome_completo='Maria Souza', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10')

    colaborador = Colaborador.all_tenants.get(cpf=CPF_VALIDO)
    assert colaborador.tenant_id == cenario['tenant'].pk
    assert colaborador.unidade_id == cenario['unidade'].pk
    assert colaborador.situacao == estados.SITUACAO_CADASTRO
    assert colaborador.origem_cadastro == 'link_publico'
    assert colaborador.ponto_entrada == estados.ENTRADA_LINK_PUBLICO


@pytest.mark.django_db
def test_cadastro_com_thread_local_de_outro_tenant_nao_vaza(cenario):
    """
    O teste que prova que estamos protegidos e nao com sorte.

    Simula o pior caso: o thread local ficou sujo com OUTRO tenant (request
    anterior num servidor que reusa thread). Se o escopo e o tenant explicito
    nao valessem, a pessoa nasceria na empresa errada.
    """
    from apps.sistema.middleware import get_current_tenant, set_current_tenant

    intruso = TenantFactory(modulo_people=True)
    set_current_tenant(intruso)
    try:
        _enviar(Client(), cenario['link'],
                nome_completo='Maria Souza', cpf=CPF_VALIDO,
                telefone='86999998888', data_nascimento='1995-04-10')
    finally:
        set_current_tenant(None)

    colaborador = Colaborador.all_tenants.get(cpf=CPF_VALIDO)
    assert colaborador.tenant_id == cenario['tenant'].pk
    assert Colaborador.all_tenants.filter(tenant=intruso).count() == 0


@pytest.mark.django_db
def test_escopo_e_restaurado_depois_da_request(cenario):
    """Se o escopo vazasse, a proxima request herdaria o tenant errado."""
    from apps.sistema.middleware import get_current_tenant

    _enviar(Client(), cenario['link'],
            nome_completo='Maria Souza', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10')

    assert get_current_tenant() is None


@pytest.mark.django_db
def test_consentimento_lgpd_e_gravado_com_versao(cenario):
    """
    Sem a versao, um aceite antigo pareceria valer pro texto novo, que e
    exatamente o que a LGPD nao aceita.
    """
    _enviar(Client(), cenario['link'],
            nome_completo='Maria Souza', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10')

    colaborador = Colaborador.all_tenants.get(cpf=CPF_VALIDO)
    assert colaborador.consentimento_lgpd is True
    assert colaborador.consentimento_lgpd_em is not None
    assert colaborador.consentimento_lgpd_versao == '1.0'


@pytest.mark.django_db
def test_sem_consentimento_nao_cadastra(cenario):
    cliente = Client()
    resposta = cliente.post(f'/people/publico/{cenario["link"].token}/enviar/', {
        'nome_completo': 'Maria Souza', 'cpf': CPF_VALIDO,
        'telefone': '86999998888', 'data_nascimento': '1995-04-10',
    })

    assert resposta.status_code == 400
    assert not Colaborador.all_tenants.filter(cpf=CPF_VALIDO).exists()


@pytest.mark.django_db
def test_campo_obrigatorio_faltando_volta_com_erro(cenario):
    resposta = _enviar(Client(), cenario['link'], cpf=CPF_VALIDO)
    assert resposta.status_code == 400
    assert not Colaborador.all_tenants.filter(cpf=CPF_VALIDO).exists()


@pytest.mark.django_db
def test_campo_fora_do_template_e_ignorado(cenario):
    """Quem posta aqui e a internet. Campo desconhecido nao pode virar coluna."""
    _enviar(Client(), cenario['link'],
            nome_completo='Maria Souza', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10',
            situacao='efetivado', pendente_revisao='False',
            elegivel_recontratacao='False')

    colaborador = Colaborador.all_tenants.get(cpf=CPF_VALIDO)
    assert colaborador.situacao == estados.SITUACAO_CADASTRO
    assert colaborador.elegivel_recontratacao is True


@pytest.mark.django_db
def test_submissao_e_registrada(cenario):
    _enviar(Client(), cenario['link'],
            nome_completo='Maria Souza', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10')

    submissao = SubmissaoLinkCadastro.all_tenants.get(link=cenario['link'])
    assert submissao.resultado == 'criado'
    assert CPF_VALIDO not in str(submissao.payload)  # CPF mascarado
    cenario['link'].refresh_from_db()
    assert cenario['link'].submissoes == 1


# ──────────────────────────────────────────────
# Dedup pela porta publica
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_mesmo_cpf_nao_cria_segunda_pessoa(cenario):
    registrar_colaborador(
        cenario['tenant'], cenario['unidade'],
        {'nome_completo': 'Maria Souza', 'cpf': CPF_VALIDO}, origem='rh')

    _enviar(Client(), cenario['link'],
            nome_completo='Maria S. Souza', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10')

    assert Colaborador.all_tenants.filter(tenant=cenario['tenant']).count() == 1


@pytest.mark.django_db
def test_conflito_nao_revela_que_a_pessoa_existe(cenario):
    """
    A pagina e aberta na internet. Dizer "esse CPF ja esta cadastrado" a
    transformaria num oraculo de quem trabalha na empresa.
    """
    registrar_colaborador(
        cenario['tenant'], cenario['unidade'],
        {'nome_completo': 'Maria Souza', 'cpf': CPF_VALIDO_2,
         'telefone': '5586999998888'}, origem='rh')

    resposta = _enviar(Client(), cenario['link'],
                       nome_completo='Joana Lima', cpf=CPF_VALIDO,
                       telefone='86999998888', data_nascimento='1995-04-10')

    corpo = resposta.content.decode()
    assert resposta.status_code == 409
    assert 'Procure o RH' in corpo
    # Nada de QUEM JA EXISTE pode aparecer. O CPF que o proprio remetente
    # digitou volta no campo, e isso e certo: senao ele redigita tudo.
    assert 'Maria Souza' not in corpo
    assert CPF_VALIDO_2 not in corpo


@pytest.mark.django_db
def test_conflito_e_registrado_pro_rh_investigar(cenario):
    registrar_colaborador(
        cenario['tenant'], cenario['unidade'],
        {'nome_completo': 'Maria Souza', 'telefone': '5586999998888'}, origem='rh')

    _enviar(Client(), cenario['link'],
            nome_completo='Joana Lima', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10')

    submissao = SubmissaoLinkCadastro.all_tenants.get(link=cenario['link'])
    assert submissao.resultado == 'rejeitado'
    assert submissao.erro == 'possivel_duplicata'


@pytest.mark.django_db
def test_desligado_que_se_recadastra_e_reativado(cenario):
    resultado = registrar_colaborador(
        cenario['tenant'], cenario['unidade'],
        {'nome_completo': 'Maria Souza', 'cpf': CPF_VALIDO}, origem='rh')
    mover_situacao(resultado.colaborador, estados.SITUACAO_DESLIGADO,
                   motivo='Nao compareceu')

    _enviar(Client(), cenario['link'],
            nome_completo='Maria Souza', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10')

    assert Colaborador.all_tenants.filter(tenant=cenario['tenant']).count() == 1
    colaborador = Colaborador.all_tenants.get(cpf=CPF_VALIDO)
    assert colaborador.situacao == estados.SITUACAO_CADASTRO


# ──────────────────────────────────────────────
# Anti abuso
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_honeypot_finge_sucesso_e_nao_cadastra(cenario):
    """Responder erro ensinaria o robo. Respondemos sucesso e registramos."""
    resposta = _enviar(Client(), cenario['link'],
                       nome_completo='Robo', cpf=CPF_VALIDO,
                       telefone='86999998888', data_nascimento='1995-04-10',
                       **{NOME_HONEYPOT: 'preenchido por robo'})

    assert resposta.status_code == 200
    assert not Colaborador.all_tenants.filter(cpf=CPF_VALIDO).exists()
    submissao = SubmissaoLinkCadastro.all_tenants.get(link=cenario['link'])
    assert submissao.resultado == 'rejeitado'
    assert submissao.erro == 'honeypot'


@pytest.mark.django_db
def test_honeypot_nao_conta_no_teto_do_link(cenario):
    """Senao um robo derrubaria o cadastro da loja so mandando lixo."""
    cenario['link'].max_submissoes = 2
    cenario['link'].save()

    for _ in range(3):
        _enviar(Client(), cenario['link'], nome_completo='Robo',
                **{NOME_HONEYPOT: 'x'})

    cenario['link'].refresh_from_db()
    assert cenario['link'].submissoes == 0
    assert cenario['link'].ativo is True


@pytest.mark.django_db
def test_link_se_fecha_ao_bater_o_teto(cenario):
    cenario['link'].max_submissoes = 1
    cenario['link'].save()

    _enviar(Client(), cenario['link'],
            nome_completo='Primeira', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10')

    cenario['link'].refresh_from_db()
    assert cenario['link'].ativo is False
    assert Client().get(_url(cenario['link'])).status_code == 404


@pytest.mark.django_db
def test_get_no_endpoint_de_envio_e_recusado(cenario):
    assert Client().get(f'/people/publico/{cenario["link"].token}/enviar/').status_code == 405


@pytest.mark.django_db
def test_rate_limit_por_ip(cenario, settings):
    """O unico teste com rate limit ligado. Os outros o desligam de proposito."""
    settings.RATELIMIT_ENABLE = True
    cliente = Client()

    respostas = [
        _enviar(cliente, cenario['link'], nome_completo=f'Pessoa {i}')
        for i in range(7)
    ]
    # block=True levanta Ratelimited, que herda de PermissionDenied: 403.
    assert any(r.status_code == 403 for r in respostas), \
        'rate limit por IP nao disparou'


# ──────────────────────────────────────────────
# Formulario configuravel
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_formulario_usa_o_template_do_link(cenario):
    """O link aponta pro template, e e ele que decide quais campos aparecem."""
    campos = config_padrao()
    campos['nome_completo']['rotulo'] = 'Seu nome'
    campos['telefone']['rotulo'] = 'Seu WhatsApp'
    campos['cpf'] = {'solicitar': False, 'obrigatorio': False, 'rotulo': 'CPF'}
    template = TemplateFormulario.all_tenants.create(
        tenant=cenario['tenant'], nome='Curto', campos=campos)
    cenario['unidade'].exige_cpf_no_autocadastro = False
    cenario['unidade'].save()
    cenario['link'].template = template
    cenario['link'].save()

    corpo = Client().get(_url(cenario['link'])).content.decode()
    assert 'Seu nome' in corpo
    assert 'Seu WhatsApp' in corpo
    assert 'name="cpf"' not in corpo


@pytest.mark.django_db
def test_campo_desligado_no_template_nao_e_aceito_no_post(cenario):
    """Nao basta esconder na tela: o POST tambem precisa ignorar."""
    campos = config_padrao()
    campos['email'] = {'solicitar': False, 'obrigatorio': False, 'rotulo': 'Email'}
    template = TemplateFormulario.all_tenants.create(
        tenant=cenario['tenant'], nome='Sem email', campos=campos)
    cenario['link'].template = template
    cenario['link'].save()

    _enviar(Client(), cenario['link'],
            nome_completo='Maria Souza', cpf=CPF_VALIDO,
            telefone='86999998888', data_nascimento='1995-04-10',
            email='naodeviaentrar@exemplo.com')

    colaborador = Colaborador.all_tenants.get(nome_completo='Maria Souza')
    assert colaborador.email == ''


@pytest.mark.django_db
def test_sem_template_usa_o_padrao_do_tenant(cenario):
    assert cenario['link'].template is None
    corpo = Client().get(_url(cenario['link'])).content.decode()
    assert 'name="nome_completo"' in corpo
    assert TemplateFormulario.all_tenants.filter(
        tenant=cenario['tenant'], padrao=True).exists()


@pytest.mark.django_db
def test_cpf_obrigatorio_quando_a_configuracao_exige(cenario):
    """A exigencia de CPF vem da config, nao do template: e ela que sustenta o dedup."""
    resposta = _enviar(Client(), cenario['link'],
                       nome_completo='Maria Souza', telefone='86999998888',
                       data_nascimento='1995-04-10')

    assert resposta.status_code == 400
    assert not Colaborador.all_tenants.filter(nome_completo='Maria Souza').exists()


@pytest.mark.django_db
def test_unidade_pode_afrouxar_a_exigencia_de_cpf(cenario):
    """
    O override por unidade vale aqui tambem. Sem CPF a pessoa entra, mas cai na
    fila de revisao do RH, porque o dedup dela ficou fraco.
    """
    cenario['unidade'].exige_cpf_no_autocadastro = False
    cenario['unidade'].save()

    campos = config_padrao()
    campos['cpf'] = {'solicitar': False, 'obrigatorio': False, 'rotulo': 'CPF'}
    template = TemplateFormulario.all_tenants.create(
        tenant=cenario['tenant'], nome='Sem CPF', campos=campos)
    cenario['link'].template = template
    cenario['link'].save()

    _enviar(Client(), cenario['link'],
            nome_completo='Maria Souza', telefone='86999998888',
            data_nascimento='1995-04-10')

    colaborador = Colaborador.all_tenants.get(nome_completo='Maria Souza')
    assert colaborador.cpf is None
    assert colaborador.pendente_revisao is True
