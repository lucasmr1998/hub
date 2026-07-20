"""
Testes da ficha do colaborador.

O ponto sensivel aqui e a fronteira: a ficha edita QUEM a pessoa e, o board muda
EM QUE FASE ela esta. Se a ficha conseguisse mexer em fase ou nas datas de
vinculo, existiria um caminho de mudanca sem historico, e a trilha deixaria de
ser confiavel justamente pro que ela serve.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.people import estados
from apps.people.models import Colaborador, Unidade
from apps.people.services import mover_situacao, registrar_colaborador
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


CPF_VALIDO = '52998224725'
CPF_VALIDO_2 = '15350946056'
TODAS = ['people.ver', 'people.criar_colaborador', 'people.mover_colaborador']


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant, nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro', codigo='loja-centro')
    return {'tenant': tenant, 'unidade': unidade}


def _cliente(tenant, username='gestora', funcionalidades=TODAS):
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=tenant)
    perfil = PerfilPermissao.objects.create(tenant=tenant, nome=f'Perfil {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil)
    cliente = Client()
    cliente.force_login(user)
    return cliente


def _colaborador(cenario, nome='Maria Souza', **dados):
    return registrar_colaborador(
        cenario['tenant'], cenario['unidade'],
        {'nome_completo': nome, **dados}, origem='rh',
    ).colaborador


def _dados_edicao(colaborador, **extra):
    """Payload completo do form de dados pessoais."""
    base = {
        'nome_completo': colaborador.nome_completo,
        'primeiro_nome': colaborador.primeiro_nome,
        'cpf': colaborador.cpf or '',
        'rg': '', 'pis': '', 'data_nascimento': '',
        'telefone': colaborador.telefone or '', 'email': colaborador.email or '',
        'cep': '', 'rua': '', 'numero': '', 'complemento': '', 'bairro': '',
        'cidade': '', 'estado': '',
        'tipo_chave_pix': '', 'chave_pix': '',
        'cargo': colaborador.cargo_id or '', 'regime_contratacao': '',
        'elegivel_recontratacao': 'on',
        'observacoes': '',
    }
    base.update(extra)
    return base


# ──────────────────────────────────────────────
# A ficha abre
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_ficha_abre_com_as_tres_abas(cenario):
    """
    Tres, nao onze. Quatro das que faltam sao de fases que ainda nao existem, e
    quatro (Ocorrencias, Afastamentos, Atestados, Faltas) nenhuma fonte descreve.
    """
    colaborador = _colaborador(cenario)
    resposta = _cliente(cenario['tenant']).get(f'/people/colaboradores/{colaborador.pk}/')

    assert resposta.status_code == 200
    ids = [aba['id'] for aba in resposta.context['abas']]
    assert ids == ['aba-resumo', 'aba-dados', 'aba-historico']


@pytest.mark.django_db
def test_resumo_mostra_os_destinos_da_maquina(cenario):
    colaborador = _colaborador(cenario)
    resposta = _cliente(cenario['tenant']).get(f'/people/colaboradores/{colaborador.pk}/')

    destinos = [d['situacao'] for d in resposta.context['destinos']]
    assert destinos == estados.destinos_possiveis(estados.SITUACAO_CADASTRO)


@pytest.mark.django_db
def test_historico_aparece_em_ordem_decrescente(cenario):
    colaborador = _colaborador(cenario, data_admissao=date(2026, 7, 1))
    mover_situacao(colaborador, estados.SITUACAO_EM_ADMISSAO, motivo='Documentos ok')

    resposta = _cliente(cenario['tenant']).get(f'/people/colaboradores/{colaborador.pk}/')
    historico = list(resposta.context['historico'])

    assert len(historico) == 2
    assert historico[0].para == estados.SITUACAO_EM_ADMISSAO  # mais recente primeiro
    assert historico[1].de == ''                              # entrada na maquina


@pytest.mark.django_db
def test_ficha_de_outro_tenant_da_404(cenario):
    outro = TenantFactory(modulo_people=True)
    alheia = Unidade.all_tenants.create(tenant=outro, nome='Alheia', codigo='alheia')
    vitima = registrar_colaborador(
        outro, alheia, {'nome_completo': 'Alheia'}, origem='rh').colaborador

    resposta = _cliente(cenario['tenant']).get(f'/people/colaboradores/{vitima.pk}/')
    assert resposta.status_code == 404


# ──────────────────────────────────────────────
# Editar dados pessoais
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_edita_dados_pessoais(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    cliente.post(f'/people/colaboradores/{colaborador.pk}/',
                 _dados_edicao(colaborador, email='maria@exemplo.com', cidade='Teresina',
                               estado='pi', cep='64000000'))

    colaborador.refresh_from_db()
    assert colaborador.email == 'maria@exemplo.com'
    assert colaborador.estado == 'PI'
    assert colaborador.cep == '64000-000'


@pytest.mark.django_db
def test_edicao_nao_muda_a_fase(cenario):
    """
    A fronteira. Se a ficha pudesse mexer em situacao, existiria mudanca sem
    historico, e a trilha deixaria de servir pro que existe.
    """
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    cliente.post(f'/people/colaboradores/{colaborador.pk}/',
                 _dados_edicao(colaborador, situacao=estados.SITUACAO_EFETIVADO))

    colaborador.refresh_from_db()
    assert colaborador.situacao == estados.SITUACAO_CADASTRO


@pytest.mark.django_db
def test_edicao_nao_mexe_nas_datas_de_vinculo(cenario):
    """Elas sao calculadas pelas transicoes, nao digitadas na ficha."""
    colaborador = _colaborador(cenario, data_admissao=date(2026, 7, 1))
    mover_situacao(colaborador, estados.SITUACAO_EM_EXPERIENCIA)
    colaborador.refresh_from_db()
    fim_original = colaborador.data_fim_experiencia
    cliente = _cliente(cenario['tenant'])

    cliente.post(f'/people/colaboradores/{colaborador.pk}/',
                 _dados_edicao(colaborador, data_admissao='2020-01-01',
                               data_fim_experiencia='2020-01-01'))

    colaborador.refresh_from_db()
    assert colaborador.data_admissao == date(2026, 7, 1)
    assert colaborador.data_fim_experiencia == fim_original


@pytest.mark.django_db
def test_cpf_de_outra_pessoa_vira_erro_de_campo(cenario):
    """
    Sem esta checagem, corrigir um CPF pra um que ja existe daria IntegrityError
    500 vindo da unique, longe da causa e sem dizer de quem e o CPF.
    """
    outra = _colaborador(cenario, 'Ja Tem Esse CPF', cpf=CPF_VALIDO)
    colaborador = _colaborador(cenario, 'Maria Souza')
    cliente = _cliente(cenario['tenant'])

    resposta = cliente.post(f'/people/colaboradores/{colaborador.pk}/',
                            _dados_edicao(colaborador, cpf=CPF_VALIDO))

    assert resposta.status_code == 200
    assert outra.nome_completo.encode() in resposta.content
    colaborador.refresh_from_db()
    assert colaborador.cpf is None


@pytest.mark.django_db
def test_manter_o_proprio_cpf_nao_acusa_conflito(cenario):
    colaborador = _colaborador(cenario, cpf=CPF_VALIDO)
    cliente = _cliente(cenario['tenant'])

    cliente.post(f'/people/colaboradores/{colaborador.pk}/',
                 _dados_edicao(colaborador, cpf=CPF_VALIDO))

    colaborador.refresh_from_db()
    assert colaborador.cpf == CPF_VALIDO


@pytest.mark.django_db
def test_desmarcar_elegivel_recontratacao_bloqueia_readmissao(cenario):
    """
    O campo existe pra isso. Depois de desmarcado na ficha, o dedup recusa
    reativar essa pessoa em vez de readmiti-la sozinho.
    """
    colaborador = _colaborador(cenario, cpf=CPF_VALIDO, data_admissao=date(2026, 1, 10))
    mover_situacao(colaborador, estados.SITUACAO_DESLIGADO,
                   dados={'data_desligamento': date(2026, 6, 1),
                          'motivo_desligamento': 'justa_causa'})
    cliente = _cliente(cenario['tenant'])

    dados = _dados_edicao(colaborador, cpf=CPF_VALIDO)
    dados.pop('elegivel_recontratacao')  # checkbox desmarcado nao vai no POST
    cliente.post(f'/people/colaboradores/{colaborador.pk}/', dados)

    colaborador.refresh_from_db()
    assert colaborador.elegivel_recontratacao is False

    resultado = registrar_colaborador(
        cenario['tenant'], cenario['unidade'],
        {'nome_completo': 'Maria Souza', 'cpf': CPF_VALIDO}, origem='rh')
    assert resultado.acao == 'conflito'
    assert resultado.motivo_conflito == 'nao_elegivel_recontratacao'


# ──────────────────────────────────────────────
# Fila de revisao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_ficha_avisa_por_que_esta_pendente_de_revisao(cenario):
    colaborador = _colaborador(cenario)  # sem CPF
    resposta = _cliente(cenario['tenant']).get(f'/people/colaboradores/{colaborador.pk}/')

    assert colaborador.pendente_revisao is True
    assert b'Falta o CPF' in resposta.content


@pytest.mark.django_db
def test_marcar_revisado_tira_da_fila(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    cliente.post(f'/people/colaboradores/{colaborador.pk}/revisar/')

    colaborador.refresh_from_db()
    assert colaborador.pendente_revisao is False


@pytest.mark.django_db
def test_revisar_so_aceita_post(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])
    assert cliente.get(f'/people/colaboradores/{colaborador.pk}/revisar/').status_code == 405


# ──────────────────────────────────────────────
# Permissao
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_quem_so_ve_abre_a_ficha(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])

    resposta = cliente.get(f'/people/colaboradores/{colaborador.pk}/')
    assert resposta.status_code == 200
    assert resposta.context['pode_editar'] is False


@pytest.mark.django_db
def test_quem_so_ve_nao_salva(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])

    cliente.post(f'/people/colaboradores/{colaborador.pk}/',
                 _dados_edicao(colaborador, email='hackeado@exemplo.com'))

    colaborador.refresh_from_db()
    assert colaborador.email == ''


@pytest.mark.django_db
def test_quem_so_ve_nao_marca_revisado(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])

    assert cliente.post(f'/people/colaboradores/{colaborador.pk}/revisar/').status_code == 403
    colaborador.refresh_from_db()
    assert colaborador.pendente_revisao is True


@pytest.mark.django_db
def test_card_do_board_leva_pra_ficha(cenario):
    colaborador = _colaborador(cenario)
    corpo = _cliente(cenario['tenant']).get('/people/').content.decode()
    assert f'/people/colaboradores/{colaborador.pk}/' in corpo
