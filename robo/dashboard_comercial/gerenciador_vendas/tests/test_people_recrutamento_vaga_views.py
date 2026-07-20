"""
CRUD de vaga: views, permissao e render.

Os testes de render existem por experiencia recente neste modulo: template com
erro de sintaxe, componente recebendo formato errado e classe de CSS inexistente
passam por `manage.py check` e por teste de model sem reclamar, e so aparecem
quando alguem abre a pagina.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people import estados_recrutamento as estados_rs
from apps.people.models import Cargo, Unidade
from apps.people.models_recrutamento import (
    JUSTIFICATIVA_AUMENTO, JUSTIFICATIVA_SUBSTITUICAO,
)
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


TODAS = ['people.ver', 'people.gerir_vagas']


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo}


def _cliente(cenario, username='rh_vagas', funcionalidades=TODAS):
    """Mesmo formato do helper de tests/test_people_configuracao.py."""
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'],
                                            nome=f'Perfil {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'],
                                    perfil=perfil)
    cliente = Client()
    cliente.force_login(user)
    return cliente


def _vaga(cenario, **kwargs):
    from apps.people.models import Vaga

    dados = {'tenant': cenario['tenant'], 'unidade': cenario['unidade'],
             'cargo': cenario['cargo'], 'justificativa': JUSTIFICATIVA_AUMENTO}
    dados.update(kwargs)
    return Vaga.all_tenants.create(**dados)


# ── Render ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_lista_de_vagas_renderiza_vazia(cenario):
    resposta = _cliente(cenario).get(reverse('people:vagas_lista'))

    assert resposta.status_code == 200
    assert 'Nenhuma vaga' in resposta.content.decode()


@pytest.mark.django_db
def test_lista_mostra_a_vaga_e_o_status(cenario):
    _vaga(cenario, titulo='Atendente noturno')

    resposta = _cliente(cenario).get(reverse('people:vagas_lista'))
    corpo = resposta.content.decode()

    assert 'Atendente noturno' in corpo
    assert 'Rascunho' in corpo


@pytest.mark.django_db
def test_formulario_de_vaga_nova_renderiza(cenario):
    resposta = _cliente(cenario).get(reverse('people:vaga_criar'))

    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    # O select tem que sair com a unidade do tenant, e nao com o nome do dict
    assert 'Loja Centro' in corpo
    assert 'value' not in corpo.split('<select name="unidade"')[1].split('</select>')[0].replace('value=', '')


@pytest.mark.django_db
def test_pagina_da_vaga_renderiza_com_requisitos(cenario):
    from apps.people.models import RequisitoVaga

    vaga = _vaga(cenario)
    RequisitoVaga.all_tenants.create(tenant=cenario['tenant'], vaga=vaga,
                                     texto='Disponibilidade aos domingos')

    resposta = _cliente(cenario).get(reverse('people:vaga_editar', args=[vaga.pk]))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert 'Disponibilidade aos domingos' in corpo


# ── Criacao ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_criar_vaga_leva_pra_edicao_e_nao_pra_lista(cenario):
    """
    Vaga sem requisito ainda nao serve pra publicar. Mandar pra lista faria o
    usuario achar que acabou.
    """
    from apps.people.models import Vaga

    resposta = _cliente(cenario).post(reverse('people:vaga_criar'), {
        'unidade': cenario['unidade'].pk,
        'cargo': cenario['cargo'].pk,
        'justificativa': JUSTIFICATIVA_AUMENTO,
        'limite_aprovados': 50,
    })

    vaga = Vaga.all_tenants.get(tenant=cenario['tenant'])
    assert resposta.status_code == 302
    assert resposta.url == reverse('people:vaga_editar', args=[vaga.pk])
    # Autoria registrada: sem isto ninguem sabe quem abriu a vaga
    assert vaga.criada_por is not None
    assert vaga.criada_por.username == 'rh_vagas'


@pytest.mark.django_db
def test_substituicao_sem_indicar_quem_sai_e_recusada(cenario):
    """
    E o que evita a loja contratar e esquecer de desligar quem sai, virando
    custo dobrado. A spec descreve esse esquecimento como problema real.
    """
    from apps.people.models import Vaga

    resposta = _cliente(cenario).post(reverse('people:vaga_criar'), {
        'unidade': cenario['unidade'].pk,
        'cargo': cenario['cargo'].pk,
        'justificativa': JUSTIFICATIVA_SUBSTITUICAO,
        'limite_aprovados': 50,
    })

    assert resposta.status_code == 200
    assert not Vaga.all_tenants.filter(tenant=cenario['tenant']).exists()
    assert 'substitu' in resposta.content.decode().lower()


@pytest.mark.django_db
def test_limite_de_aprovados_zero_e_recusado_pelo_form(cenario):
    """O banco recusaria com IntegrityError. O form transforma em mensagem."""
    from apps.people.models import Vaga

    resposta = _cliente(cenario).post(reverse('people:vaga_criar'), {
        'unidade': cenario['unidade'].pk,
        'cargo': cenario['cargo'].pk,
        'justificativa': JUSTIFICATIVA_AUMENTO,
        'limite_aprovados': 0,
    })

    assert resposta.status_code == 200
    assert not Vaga.all_tenants.filter(tenant=cenario['tenant']).exists()


@pytest.mark.django_db
def test_form_nao_aceita_unidade_de_outro_tenant(cenario):
    """
    O ForeignKey.validate() so confere existencia, nao dono. Sem o queryset
    filtrado no form, um POST forjado criaria vaga apontando pra loja alheia.
    """
    from apps.sistema.models import Tenant
    from apps.people.models import Vaga

    outro = Tenant.objects.create(nome='Rede Alheia', slug='rede-alheia',
                                  modulo_people=True)
    unidade_alheia = Unidade.all_tenants.create(tenant=outro, nome='Loja Deles',
                                                codigo='deles')

    resposta = _cliente(cenario).post(reverse('people:vaga_criar'), {
        'unidade': unidade_alheia.pk,
        'cargo': cenario['cargo'].pk,
        'justificativa': JUSTIFICATIVA_AUMENTO,
        'limite_aprovados': 50,
    })

    assert resposta.status_code == 200
    assert not Vaga.all_tenants.filter(unidade=unidade_alheia).exists()


# ── Requisitos ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_adicionar_requisito(cenario):
    vaga = _vaga(cenario)

    _cliente(cenario).post(reverse('people:vaga_requisito_criar', args=[vaga.pk]), {
        'texto': 'Experiência mínima de 6 meses',
        'aparece_no_anuncio': '',
        'usar_na_triagem': 'on',
    })

    requisito = vaga.requisitos.get()
    assert requisito.usar_na_triagem
    assert not requisito.aparece_no_anuncio
    assert requisito.ordem == 1


@pytest.mark.django_db
def test_requisito_sem_uso_nenhum_e_recusado_com_mensagem(cenario):
    vaga = _vaga(cenario)

    resposta = _cliente(cenario).post(
        reverse('people:vaga_requisito_criar', args=[vaga.pk]),
        {'texto': 'Nada', 'aparece_no_anuncio': '', 'usar_na_triagem': ''},
        follow=True)

    assert not vaga.requisitos.exists()
    assert 'pelo menos um uso' in resposta.content.decode()


@pytest.mark.django_db
def test_ordem_do_requisito_incrementa(cenario):
    vaga = _vaga(cenario)
    cliente = _cliente(cenario)

    for texto in ['Primeiro', 'Segundo']:
        cliente.post(reverse('people:vaga_requisito_criar', args=[vaga.pk]),
                     {'texto': texto, 'aparece_no_anuncio': 'on'})

    assert [r.ordem for r in vaga.requisitos.all()] == [1, 2]


@pytest.mark.django_db
def test_remover_requisito_de_outra_vaga_da_404(cenario):
    from apps.people.models import RequisitoVaga

    vaga = _vaga(cenario)
    outra = _vaga(cenario)
    requisito = RequisitoVaga.all_tenants.create(
        tenant=cenario['tenant'], vaga=outra, texto='Da outra')

    resposta = _cliente(cenario).post(reverse(
        'people:vaga_requisito_remover', args=[vaga.pk, requisito.pk]))

    assert resposta.status_code == 404
    assert RequisitoVaga.all_tenants.filter(pk=requisito.pk).exists()


# ── Status ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_publicar_pela_tela(cenario):
    vaga = _vaga(cenario)

    _cliente(cenario).post(reverse('people:vaga_mudar_status', args=[vaga.pk]),
                           {'status': estados_rs.STATUS_VAGA_PUBLICADA})

    vaga.refresh_from_db()
    assert vaga.status == estados_rs.STATUS_VAGA_PUBLICADA
    assert vaga.publicada_em is not None


@pytest.mark.django_db
def test_transicao_invalida_vira_mensagem_e_nao_erro_500(cenario):
    vaga = _vaga(cenario)
    vaga.mudar_status(estados_rs.STATUS_VAGA_ENCERRADA)

    resposta = _cliente(cenario).post(
        reverse('people:vaga_mudar_status', args=[vaga.pk]),
        {'status': estados_rs.STATUS_VAGA_PUBLICADA}, follow=True)

    vaga.refresh_from_db()
    assert resposta.status_code == 200
    assert vaga.status == estados_rs.STATUS_VAGA_ENCERRADA
    assert 'vaga nova' in resposta.content.decode().lower()


# ── Permissao ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_quem_so_ve_nao_cria_vaga(cenario):
    cliente = _cliente(cenario, username='so_ve', funcionalidades=['people.ver'])

    assert cliente.get(reverse('people:vagas_lista')).status_code == 200
    assert cliente.get(reverse('people:vaga_criar')).status_code == 403


@pytest.mark.django_db
def test_quem_so_ve_nao_muda_status(cenario):
    vaga = _vaga(cenario)
    cliente = _cliente(cenario, username='so_ve', funcionalidades=['people.ver'])

    resposta = cliente.post(reverse('people:vaga_mudar_status', args=[vaga.pk]),
                            {'status': estados_rs.STATUS_VAGA_PUBLICADA})

    vaga.refresh_from_db()
    assert resposta.status_code == 403
    assert vaga.status == estados_rs.STATUS_VAGA_RASCUNHO


@pytest.mark.django_db
def test_vaga_de_outro_tenant_da_404(cenario):
    from apps.sistema.models import Tenant
    from apps.people.models import Vaga

    outro = Tenant.objects.create(nome='Rede Terceira', slug='rede-terceira',
                                  modulo_people=True)
    vaga_alheia = Vaga.all_tenants.create(
        tenant=outro,
        unidade=Unidade.all_tenants.create(tenant=outro, nome='X', codigo='x'),
        cargo=Cargo.all_tenants.create(tenant=outro, nome='Y'),
        justificativa=JUSTIFICATIVA_AUMENTO)

    resposta = _cliente(cenario).get(
        reverse('people:vaga_editar', args=[vaga_alheia.pk]))

    assert resposta.status_code == 404
