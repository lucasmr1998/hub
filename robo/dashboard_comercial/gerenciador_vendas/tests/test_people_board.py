"""
Testes do board e do cadastro pela UI.

O board e a unica superficie onde o gestor muda a fase de alguem, entao o que
importa aqui nao e "a pagina abre", e sim que a maquina de estados continue
mandando mesmo com um humano arrastando card: transicao invalida recusada,
campo obrigatorio pedido em vez de silenciado, e nenhuma criacao passando por
fora do dedup.
"""
import json
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.people import estados
from apps.people.models import Colaborador, HistoricoSituacao, Unidade
from apps.people.services import mover_situacao, registrar_colaborador
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


CPF_VALIDO = '52998224725'
TODAS = ['people.ver', 'people.criar_colaborador', 'people.mover_colaborador',
         'people.gerir_unidades']


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


def _mover(cliente, colaborador, situacao, dados=None):
    return cliente.post(
        f'/people/api/colaborador/{colaborador.pk}/mover/',
        data=json.dumps({'situacao': situacao, 'dados': dados or {}}),
        content_type='application/json',
    )


# ──────────────────────────────────────────────
# Board
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_board_abre_com_as_colunas_da_maquina(cenario):
    cliente = _cliente(cenario['tenant'])
    resposta = cliente.get('/people/')

    assert resposta.status_code == 200
    situacoes = [c['situacao'] for c in resposta.context['colunas']]
    assert situacoes == estados.COLUNAS_BOARD


@pytest.mark.django_db
def test_card_declara_os_destinos_permitidos(cenario):
    """
    O board bloqueia o drop antes de soltar, e pra isso o card precisa carregar
    os destinos. A regra continua sendo a da maquina: aqui e leitura.
    """
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    corpo = cliente.get('/people/').content.decode()
    esperado = ','.join(estados.destinos_possiveis(estados.SITUACAO_CADASTRO))
    assert f'data-destinos="{esperado}"' in corpo
    assert f'data-colaborador-id="{colaborador.pk}"' in corpo


@pytest.mark.django_db
def test_contador_por_coluna(cenario):
    _colaborador(cenario, 'Um')
    _colaborador(cenario, 'Dois')
    cliente = _cliente(cenario['tenant'])

    colunas = {c['situacao']: c['total'] for c in cliente.get('/people/').context['colunas']}
    assert colunas[estados.SITUACAO_CADASTRO] == 2
    assert colunas[estados.SITUACAO_EFETIVADO] == 0


@pytest.mark.django_db
def test_filtro_por_unidade(cenario):
    outra = Unidade.all_tenants.create(
        tenant=cenario['tenant'], nome='Loja Norte', codigo='loja-norte')
    _colaborador(cenario, 'Do Centro')
    registrar_colaborador(cenario['tenant'], outra, {'nome_completo': 'Do Norte'}, origem='rh')
    cliente = _cliente(cenario['tenant'])

    corpo = cliente.get(f'/people/?unidade={cenario["unidade"].pk}').content.decode()
    assert 'Do Centro' in corpo
    assert 'Do Norte' not in corpo


@pytest.mark.django_db
def test_board_nao_mostra_colaborador_de_outro_tenant(cenario):
    outro = TenantFactory(modulo_people=True)
    alheia = Unidade.all_tenants.create(tenant=outro, nome='Alheia', codigo='alheia')
    registrar_colaborador(outro, alheia, {'nome_completo': 'Pessoa Alheia'}, origem='rh')
    _colaborador(cenario, 'Pessoa Minha')
    cliente = _cliente(cenario['tenant'])

    corpo = cliente.get('/people/').content.decode()
    assert 'Pessoa Minha' in corpo
    assert 'Pessoa Alheia' not in corpo


# ──────────────────────────────────────────────
# Mover: a maquina de estados manda
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_move_e_persiste(cenario):
    colaborador = _colaborador(cenario, data_admissao=date(2026, 7, 1))
    cliente = _cliente(cenario['tenant'])

    resposta = _mover(cliente, colaborador, estados.SITUACAO_EM_ADMISSAO)

    assert resposta.status_code == 200
    assert Colaborador.all_tenants.get(pk=colaborador.pk).situacao == estados.SITUACAO_EM_ADMISSAO


@pytest.mark.django_db
def test_resposta_traz_os_novos_destinos(cenario):
    """O card precisa saber pra onde pode ir depois do movimento, senao o
    proximo arrasto seria bloqueado com base na fase antiga."""
    colaborador = _colaborador(cenario, data_admissao=date(2026, 7, 1))
    cliente = _cliente(cenario['tenant'])

    corpo = _mover(cliente, colaborador, estados.SITUACAO_EM_ADMISSAO).json()
    assert corpo['destinos'] == estados.destinos_possiveis(estados.SITUACAO_EM_ADMISSAO)


@pytest.mark.django_db
def test_transicao_invalida_e_recusada(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    resposta = _mover(cliente, colaborador, estados.SITUACAO_EFETIVADO)

    assert resposta.status_code == 400
    assert Colaborador.all_tenants.get(pk=colaborador.pk).situacao == estados.SITUACAO_CADASTRO


@pytest.mark.django_db
def test_campo_faltando_vira_pedido_e_nao_recusa_seca(cenario):
    """
    E o comportamento central da tela. Recusar sem dizer o que falta faz o card
    voltar sozinho e o gestor perder a confianca no board.
    """
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    resposta = _mover(cliente, colaborador, estados.SITUACAO_EM_ADMISSAO)

    assert resposta.status_code == 400
    corpo = resposta.json()
    assert corpo['campos_faltando'][0]['nome'] == 'data_admissao'
    assert corpo['campos_faltando'][0]['label'] == 'Data de admissao'
    assert corpo['campos_faltando'][0]['tipo'] == 'date'


@pytest.mark.django_db
def test_repetir_com_o_campo_preenchido_conclui(cenario):
    """A segunda tentativa, com o que o modal coletou, precisa passar."""
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    _mover(cliente, colaborador, estados.SITUACAO_EM_ADMISSAO)
    resposta = _mover(cliente, colaborador, estados.SITUACAO_EM_ADMISSAO,
                      {'data_admissao': '2026-07-01'})

    assert resposta.status_code == 200
    atualizado = Colaborador.all_tenants.get(pk=colaborador.pk)
    assert atualizado.situacao == estados.SITUACAO_EM_ADMISSAO
    assert atualizado.data_admissao == date(2026, 7, 1)


@pytest.mark.django_db
def test_mover_grava_historico(cenario):
    colaborador = _colaborador(cenario, data_admissao=date(2026, 7, 1))
    cliente = _cliente(cenario['tenant'])

    _mover(cliente, colaborador, estados.SITUACAO_EM_ADMISSAO)

    trilha = HistoricoSituacao.all_tenants.filter(colaborador=colaborador)
    assert trilha.count() == 2  # entrada no cadastro + esta transicao
    assert trilha.order_by('-criado_em').first().origem == 'painel'


@pytest.mark.django_db
def test_payload_invalido_nao_derruba(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    resposta = cliente.post(
        f'/people/api/colaborador/{colaborador.pk}/mover/',
        data='isso nao e json', content_type='application/json')

    assert resposta.status_code == 400


@pytest.mark.django_db
def test_mover_so_aceita_post(cenario):
    colaborador = _colaborador(cenario)
    cliente = _cliente(cenario['tenant'])

    assert cliente.get(f'/people/api/colaborador/{colaborador.pk}/mover/').status_code == 405


@pytest.mark.django_db
def test_quem_nao_pode_mover_recebe_403_em_json(cenario):
    colaborador = _colaborador(cenario, data_admissao=date(2026, 7, 1))
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])

    resposta = _mover(cliente, colaborador, estados.SITUACAO_EM_ADMISSAO)

    assert resposta.status_code == 403
    assert 'erro' in resposta.json()
    assert Colaborador.all_tenants.get(pk=colaborador.pk).situacao == estados.SITUACAO_CADASTRO


@pytest.mark.django_db
def test_nao_move_colaborador_de_outro_tenant(cenario):
    outro = TenantFactory(modulo_people=True)
    alheia = Unidade.all_tenants.create(tenant=outro, nome='Alheia', codigo='alheia')
    vitima = registrar_colaborador(
        outro, alheia, {'nome_completo': 'Alheia'}, origem='rh').colaborador
    cliente = _cliente(cenario['tenant'])

    assert _mover(cliente, vitima, estados.SITUACAO_EM_ADMISSAO).status_code == 404


@pytest.mark.django_db
def test_prorrogacao_pelo_board(cenario):
    """Auto transicao: o card nao se move, mas a transicao acontece."""
    colaborador = _colaborador(cenario, data_admissao=date(2026, 7, 1))
    mover_situacao(colaborador, estados.SITUACAO_EM_EXPERIENCIA)
    cliente = _cliente(cenario['tenant'])

    resposta = _mover(cliente, colaborador, estados.SITUACAO_EM_EXPERIENCIA)

    assert resposta.status_code == 200
    assert Colaborador.all_tenants.get(pk=colaborador.pk).prorrogacoes_experiencia == 1


# ──────────────────────────────────────────────
# Cadastro pela UI, com os tres pontos de entrada
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_modal_oferece_os_tres_pontos_de_entrada(cenario):
    cliente = _cliente(cenario['tenant'])
    corpo = cliente.get('/people/').content.decode()

    for entrada in ['ja_trabalhando', 'em_admissao', 'so_cadastro']:
        assert f'entrada={entrada}' in corpo


@pytest.mark.django_db
def test_cadastra_entrando_em_cadastro(cenario):
    cliente = _cliente(cenario['tenant'])

    cliente.post('/people/colaboradores/novo/?entrada=so_cadastro', {
        'nome_completo': 'Maria Souza', 'cpf': CPF_VALIDO,
        'unidade': cenario['unidade'].pk,
    })

    colaborador = Colaborador.all_tenants.get(cpf=CPF_VALIDO)
    assert colaborador.situacao == estados.SITUACAO_CADASTRO
    assert colaborador.ponto_entrada == estados.ENTRADA_SO_CADASTRO


@pytest.mark.django_db
def test_cadastra_ja_trabalhando_entra_em_experiencia(cenario):
    cliente = _cliente(cenario['tenant'])

    cliente.post('/people/colaboradores/novo/?entrada=ja_trabalhando', {
        'nome_completo': 'Maria Souza', 'cpf': CPF_VALIDO,
        'unidade': cenario['unidade'].pk, 'data_admissao': '2026-07-01',
    })

    colaborador = Colaborador.all_tenants.get(cpf=CPF_VALIDO)
    assert colaborador.situacao == estados.SITUACAO_EM_EXPERIENCIA
    assert colaborador.ponto_entrada == estados.ENTRADA_JA_TRABALHANDO


@pytest.mark.django_db
def test_entrada_que_exige_data_barra_sem_ela(cenario):
    """A exigencia vem da maquina de estados, nao de regra escrita no form."""
    cliente = _cliente(cenario['tenant'])

    resposta = cliente.post('/people/colaboradores/novo/?entrada=em_admissao', {
        'nome_completo': 'Maria Souza', 'unidade': cenario['unidade'].pk,
    })

    assert resposta.status_code == 200
    assert not Colaborador.all_tenants.filter(nome_completo='Maria Souza').exists()


@pytest.mark.django_db
def test_entrada_desconhecida_cai_no_cadastro(cenario):
    """Nao confiar em querystring: qualquer valor estranho vira o ponto mais
    conservador."""
    cliente = _cliente(cenario['tenant'])

    resposta = cliente.get('/people/colaboradores/novo/?entrada=efetivado')
    assert resposta.context['situacao_inicial'] == estados.SITUACAO_CADASTRO


@pytest.mark.django_db
def test_link_publico_nao_e_ponto_de_entrada_da_ui(cenario):
    """Aquele ponto pertence ao formulario publico, nao ao RH."""
    cliente = _cliente(cenario['tenant'])

    resposta = cliente.get('/people/colaboradores/novo/?entrada=link_publico')
    assert resposta.context['entrada'] == estados.ENTRADA_SO_CADASTRO


@pytest.mark.django_db
def test_duplicata_mostra_os_candidatos_em_vez_de_criar(cenario):
    _colaborador(cenario, 'Maria Souza', telefone='86999998888')
    cliente = _cliente(cenario['tenant'])

    resposta = cliente.post('/people/colaboradores/novo/?entrada=so_cadastro', {
        'nome_completo': 'Joana Lima', 'telefone': '86999998888',
        'unidade': cenario['unidade'].pk,
    })

    assert resposta.status_code == 200
    assert len(resposta.context['conflitos']) == 1
    assert Colaborador.all_tenants.filter(tenant=cenario['tenant']).count() == 1


@pytest.mark.django_db
def test_rh_confirma_que_e_a_mesma_pessoa(cenario):
    existente = _colaborador(cenario, 'Maria Souza', telefone='86999998888')
    cliente = _cliente(cenario['tenant'])

    cliente.post('/people/colaboradores/novo/?entrada=so_cadastro', {
        'nome_completo': 'Maria S. Souza', 'telefone': '86999998888',
        'cpf': CPF_VALIDO, 'unidade': cenario['unidade'].pk,
        'resolver_como': existente.pk,
    })

    assert Colaborador.all_tenants.filter(tenant=cenario['tenant']).count() == 1
    existente.refresh_from_db()
    assert existente.cpf == CPF_VALIDO


@pytest.mark.django_db
def test_quem_nao_pode_criar_nao_ve_o_botao(cenario):
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])
    corpo = cliente.get('/people/').content.decode()
    assert 'Novo colaborador' not in corpo


@pytest.mark.django_db
def test_quem_nao_pode_criar_e_barrado_no_post(cenario):
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])

    resposta = cliente.post('/people/colaboradores/novo/?entrada=so_cadastro', {
        'nome_completo': 'Maria', 'unidade': cenario['unidade'].pk})

    assert resposta.status_code == 403
    assert not Colaborador.all_tenants.filter(nome_completo='Maria').exists()
