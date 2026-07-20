"""
Campos configuraveis da candidatura, por vaga.

O que este arquivo defende: o RH escolhe os campos por vaga, os travados (nome,
WhatsApp) nao se desligam nunca, e um campo desligado nao pode ser exigido nem
gravado. E o catalogo espelha campos_formulario do DP, entao segue as mesmas
garantias.
"""
import secrets

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people import campos_candidatura as catalogo
from apps.people.models import Cargo, Candidato, LinkCandidatura, Unidade, Vaga
from apps.people.models_recrutamento import JUSTIFICATIVA_AUMENTO
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   justificativa=JUSTIFICATIVA_AUMENTO)
    vaga.mudar_status('publicada')
    link = LinkCandidatura.all_tenants.create(
        tenant=tenant, vaga=vaga, unidade=unidade, canal='facebook',
        token=secrets.token_urlsafe(32))
    return {'tenant': tenant, 'unidade': unidade, 'vaga': vaga, 'link': link}


@pytest.fixture(autouse=True)
def sem_rate_limit(settings):
    settings.RATELIMIT_ENABLE = False


def _cliente(cenario):
    user = User.objects.create_user(username='rh_campos', password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'], nome='P')
    for codigo in ['people.ver', 'people.gerir_vagas']:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


def _payload(**extra):
    dados = {'nome_completo': 'Maria', 'whatsapp': '86999998888',
             'consentimento_lgpd': 'on'}
    dados.update(extra)
    return dados


# ── Catalogo (puro) ──────────────────────────────────────────────────────────

def test_nome_e_whatsapp_sao_travados():
    assert 'nome_completo' in catalogo.CAMPOS_TRAVADOS
    assert 'whatsapp' in catalogo.CAMPOS_TRAVADOS


def test_config_vazia_usa_o_padrao():
    config = catalogo.normalizar_config({})
    assert config['nome_completo']['solicitar'] is True
    assert config['email']['solicitar'] is True


def test_travado_nao_pode_ser_desligado():
    """Mesmo mandando solicitar=False, o travado volta True."""
    config = catalogo.normalizar_config({
        'whatsapp': {'solicitar': False, 'obrigatorio': False}})
    assert config['whatsapp']['solicitar'] is True
    assert config['whatsapp']['obrigatorio'] is True


def test_campo_nao_solicitado_nao_pode_ser_obrigatorio():
    """Formulario impossivel de enviar nao pode ser configurado."""
    config = catalogo.normalizar_config({
        'email': {'solicitar': False, 'obrigatorio': True}})
    assert config['email']['obrigatorio'] is False


def test_campo_novo_no_catalogo_aparece_em_config_antiga():
    """Vaga salva antes de um campo existir nao perde o campo, ganha o padrao."""
    config = catalogo.normalizar_config({'nome_completo': {'solicitar': True}})
    # curriculo nao estava na config salva, mas existe no catalogo
    assert 'curriculo' in config


# ── Render publico segue a config ────────────────────────────────────────────

@pytest.mark.django_db
def test_form_publico_mostra_so_os_campos_solicitados(cenario):
    cenario['vaga'].config_campos = catalogo.normalizar_config({
        'nome_completo': {'solicitar': True},
        'whatsapp': {'solicitar': True},
        'email': {'solicitar': False},
        'cidade': {'solicitar': False},
        'experiencia_previa': {'solicitar': True},
    })
    cenario['vaga'].save()

    corpo = Client().get(
        reverse('people_candidatura:formulario', args=[cenario['link'].token])
    ).content.decode()

    assert 'name="nome_completo"' in corpo
    assert 'name="experiencia_previa"' in corpo
    assert 'name="email"' not in corpo
    assert 'name="cidade"' not in corpo


@pytest.mark.django_db
def test_secao_sem_campo_solicitado_nao_aparece(cenario):
    """Desligou cidade, bairro, estado: a secao 'Onde voce mora' some."""
    cfg = catalogo.normalizar_config({})
    for nome in ['cidade', 'bairro', 'estado']:
        cfg[nome] = {'solicitar': False, 'obrigatorio': False, 'rotulo': ''}
    cenario['vaga'].config_campos = catalogo.normalizar_config(cfg)
    cenario['vaga'].save()

    corpo = Client().get(
        reverse('people_candidatura:formulario', args=[cenario['link'].token])
    ).content.decode()

    assert 'Onde você mora' not in corpo


# ── Validacao segue a config ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_campo_marcado_obrigatorio_e_exigido(cenario):
    cenario['vaga'].config_campos = catalogo.normalizar_config({
        **catalogo.PADRAO,
        'cidade': {'solicitar': True, 'obrigatorio': True},
    })
    cenario['vaga'].save()

    resposta = Client().post(
        reverse('people_candidatura:enviar', args=[cenario['link'].token]),
        _payload())  # sem cidade

    assert resposta.status_code == 400
    assert not Candidato.all_tenants.filter(tenant=cenario['tenant']).exists()


@pytest.mark.django_db
def test_campo_desligado_nao_e_gravado_mesmo_se_vier_no_post(cenario):
    """
    Seguranca: campo que a vaga nao pede nao entra, mesmo num POST forjado que
    inclua o campo. So o que esta solicitado e lido.
    """
    cfg = catalogo.normalizar_config({})
    cfg['experiencia_previa'] = {'solicitar': False, 'obrigatorio': False, 'rotulo': ''}
    cenario['vaga'].config_campos = catalogo.normalizar_config(cfg)
    cenario['vaga'].save()

    Client().post(
        reverse('people_candidatura:enviar', args=[cenario['link'].token]),
        _payload(experiencia_previa='Forjado'))

    candidato = Candidato.all_tenants.get(tenant=cenario['tenant'])
    assert candidato.experiencia_previa == ''


@pytest.mark.django_db
def test_whatsapp_continua_exigido_mesmo_com_config_custom(cenario):
    """Travado nao se solta por config: sem WhatsApp nao passa."""
    cenario['vaga'].config_campos = catalogo.normalizar_config({})
    cenario['vaga'].save()

    resposta = Client().post(
        reverse('people_candidatura:enviar', args=[cenario['link'].token]),
        {'nome_completo': 'Maria', 'consentimento_lgpd': 'on'})  # sem whatsapp

    assert resposta.status_code == 400
    assert not Candidato.all_tenants.filter(tenant=cenario['tenant']).exists()


# ── Salvar config pela tela da vaga ──────────────────────────────────────────

@pytest.mark.django_db
def test_salvar_campos_pela_pagina_da_vaga(cenario):
    resposta = _cliente(cenario).post(
        reverse('people:vaga_campos_salvar', args=[cenario['vaga'].pk]), {
            'solicitar_email': 'on',
            'solicitar_cidade': 'on', 'obrigatorio_cidade': 'on',
            # curriculo, experiencia etc. nao vieram: viram solicitar=False
        })

    assert resposta.status_code == 302
    cenario['vaga'].refresh_from_db()
    config = cenario['vaga'].config_campos
    assert config['cidade']['obrigatorio'] is True
    assert config['curriculo']['solicitar'] is False
    # Travado sobrevive mesmo sem vir no POST
    assert config['whatsapp']['solicitar'] is True


@pytest.mark.django_db
def test_dedup_continua_funcionando_com_campos_custom(cenario):
    """A configurabilidade nao pode ter quebrado o dedup por WhatsApp."""
    cenario['vaga'].config_campos = catalogo.normalizar_config({})
    cenario['vaga'].save()
    url = reverse('people_candidatura:enviar', args=[cenario['link'].token])

    Client().post(url, _payload())
    segunda = Client().post(url, _payload(nome_completo='Outra'))

    assert segunda.status_code == 409
    assert Candidato.all_tenants.filter(tenant=cenario['tenant']).count() == 1
