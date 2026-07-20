"""
Passo 3: link de candidatura, QR e atribuicao por canal.

O que este arquivo defende, alem do CRUD: as tres diferencas deliberadas em
relacao ao link do DP (varios por vaga, sem expiracao, sem teto) e o fato de o
texto de divulgacao SAIR da vaga em vez de ser redigitado.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people import estados_recrutamento as estados_rs
from apps.people.models import Cargo, LinkCandidatura, RequisitoVaga, Unidade, Vaga
from apps.people.models_recrutamento import JUSTIFICATIVA_AUMENTO
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
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   justificativa=JUSTIFICATIVA_AUMENTO,
                                   turno='noite')
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo, 'vaga': vaga}


def _cliente(cenario, username='rh_links', funcionalidades=TODAS):
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


def _link(cenario, **kwargs):
    import secrets

    dados = {'tenant': cenario['tenant'], 'vaga': cenario['vaga'],
             'unidade': cenario['unidade'], 'canal': 'facebook',
             'token': secrets.token_urlsafe(32)}
    dados.update(kwargs)
    return LinkCandidatura.all_tenants.create(**dados)


# ── As tres diferencas em relacao ao link do DP ──────────────────────────────

@pytest.mark.django_db
def test_varios_links_no_mesmo_canal_convivem(cenario):
    """
    Dois grupos de Facebook diferentes e caso real. Quem distingue e o apelido.
    O link do DP tinha constraint de um por unidade; aqui nao ha, de proposito.
    """
    _link(cenario, canal='facebook', apelido_interno='Grupo zona sul')
    _link(cenario, canal='facebook', apelido_interno='Grupo centro')

    assert cenario['vaga'].links.count() == 2


@pytest.mark.django_db
def test_link_nao_tem_campo_de_expiracao(cenario):
    """
    Decisao consciente da origem: publicacao antiga em grupo de Facebook
    continua rendendo candidato meses depois. Desativacao e manual.

    O teste olha o schema porque a ausencia de um campo nao quebra nada
    sozinha, e alguem poderia "consertar" adicionando expiracao sem saber que a
    falta dela e deliberada.
    """
    campos = {f.name for f in LinkCandidatura._meta.get_fields()}

    assert 'expira_em' not in campos
    assert 'max_candidaturas' not in campos


@pytest.mark.django_db
def test_link_ativo_de_vaga_publicada_aceita(cenario):
    cenario['vaga'].mudar_status(estados_rs.STATUS_VAGA_PUBLICADA)
    link = _link(cenario)

    assert link.esta_valido()


@pytest.mark.django_db
def test_link_para_de_aceitar_quando_a_vaga_pausa(cenario):
    """A vaga manda no link, e nao o contrario."""
    cenario['vaga'].mudar_status(estados_rs.STATUS_VAGA_PUBLICADA)
    link = _link(cenario)

    cenario['vaga'].mudar_status(estados_rs.STATUS_VAGA_PAUSADA)
    link.refresh_from_db()

    assert not link.esta_valido()


@pytest.mark.django_db
def test_link_desativado_nao_aceita(cenario):
    cenario['vaga'].mudar_status(estados_rs.STATUS_VAGA_PUBLICADA)
    link = _link(cenario)

    link.desativar()

    assert not link.esta_valido()
    assert link.desativado_em is not None


@pytest.mark.django_db
def test_desativar_preserva_a_linha_e_o_contador(cenario):
    """
    Apagar levaria junto a atribuicao de canal, que e a razao de o link existir.
    """
    link = _link(cenario, candidaturas=17)

    link.desativar()

    link.refresh_from_db()
    assert link.candidaturas == 17
    assert LinkCandidatura.all_tenants.filter(pk=link.pk).exists()


# ── O texto sai da vaga ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_texto_padrao_puxa_requisitos_do_anuncio(cenario):
    """
    "A vaga e a fonte da verdade" virando codigo: o RH nao redigita requisito no
    link, ele sai do que ja foi cadastrado.
    """
    RequisitoVaga.all_tenants.create(
        tenant=cenario['tenant'], vaga=cenario['vaga'],
        texto='Disponibilidade aos domingos', aparece_no_anuncio=True)

    texto = _link(cenario).texto_padrao()

    assert 'Disponibilidade aos domingos' in texto
    assert 'Loja Centro' in texto
    assert 'Noite' in texto


@pytest.mark.django_db
def test_criterio_de_triagem_calado_nao_vaza_pro_texto(cenario):
    """
    O ponto inteiro dos dois booleanos separados. Se vazasse, o mecanismo de
    "filtrar por coisa que nao convem publicar" estaria quebrado.
    """
    RequisitoVaga.all_tenants.create(
        tenant=cenario['tenant'], vaga=cenario['vaga'],
        texto='Experiência mínima de 6 meses',
        aparece_no_anuncio=False, usar_na_triagem=True)

    texto = _link(cenario).texto_padrao()

    assert 'Experiência mínima' not in texto


@pytest.mark.django_db
def test_link_sem_vaga_usa_texto_de_banco_de_talentos(cenario):
    link = _link(cenario, vaga=None)

    assert 'currículo' in link.texto_padrao()


# ── Views ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_gerar_link_pela_pagina_da_vaga(cenario):
    resposta = _cliente(cenario).post(
        reverse('people:vaga_link_criar', args=[cenario['vaga'].pk]),
        {'canal': 'facebook', 'apelido_interno': 'Grupo zona sul',
         'cta': 'Estamos contratando!'})

    link = cenario['vaga'].links.get()
    assert resposta.status_code == 302
    assert link.canal == 'facebook'
    assert link.unidade_id == cenario['unidade'].id
    assert len(link.token) > 20
    # Texto ja nasce preenchido a partir da vaga
    assert 'Estamos contratando!' in link.texto_compartilhamento


@pytest.mark.django_db
def test_token_e_diferente_a_cada_link(cenario):
    cliente = _cliente(cenario)
    for canal in ['facebook', 'instagram']:
        cliente.post(reverse('people:vaga_link_criar', args=[cenario['vaga'].pk]),
                     {'canal': canal})

    tokens = {l.token for l in cenario['vaga'].links.all()}
    assert len(tokens) == 2


@pytest.mark.django_db
def test_canal_invalido_e_recusado(cenario):
    resposta = _cliente(cenario).post(
        reverse('people:vaga_link_criar', args=[cenario['vaga'].pk]),
        {'canal': 'pombo_correio'}, follow=True)

    assert not cenario['vaga'].links.exists()
    assert 'canal' in resposta.content.decode().lower()


@pytest.mark.django_db
def test_qr_sai_em_svg_com_a_url_publica(cenario):
    link = _link(cenario)

    resposta = _cliente(cenario).get(
        reverse('people:vaga_link_qr', args=[cenario['vaga'].pk, link.pk]))

    assert resposta.status_code == 200
    assert resposta['Content-Type'] == 'image/svg+xml'
    assert 'attachment' in resposta['Content-Disposition']
    # SVG e nao PNG porque o uso real e cartaz impresso, que precisa escalar
    assert b'<svg' in resposta.content


@pytest.mark.django_db
def test_pagina_da_vaga_mostra_os_links(cenario):
    _link(cenario, apelido_interno='Grupo zona sul', candidaturas=4)

    resposta = _cliente(cenario).get(
        reverse('people:vaga_editar', args=[cenario['vaga'].pk]))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert 'Grupo zona sul' in corpo
    assert 'Divulgação' in corpo


@pytest.mark.django_db
def test_desativar_pela_tela(cenario):
    link = _link(cenario)

    _cliente(cenario).post(reverse(
        'people:vaga_link_desativar', args=[cenario['vaga'].pk, link.pk]))

    link.refresh_from_db()
    assert not link.ativo


# ── Isolamento ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_link_de_outra_vaga_da_404(cenario):
    outra = Vaga.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], justificativa=JUSTIFICATIVA_AUMENTO)
    link = _link(cenario, vaga=outra)

    resposta = _cliente(cenario).post(reverse(
        'people:vaga_link_desativar', args=[cenario['vaga'].pk, link.pk]))

    link.refresh_from_db()
    assert resposta.status_code == 404
    assert link.ativo


@pytest.mark.django_db
def test_quem_so_ve_nao_gera_link(cenario):
    cliente = _cliente(cenario, username='so_ve', funcionalidades=['people.ver'])

    resposta = cliente.post(
        reverse('people:vaga_link_criar', args=[cenario['vaga'].pk]),
        {'canal': 'facebook'})

    assert resposta.status_code == 403
    assert not cenario['vaga'].links.exists()


@pytest.mark.django_db
def test_token_e_unico_globalmente_e_nao_por_tenant(cenario):
    """
    A URL publica nao carrega tenant: o proprio token e o mecanismo que resolve
    de quem e o link. Unicidade por tenant abriria colisao entre tenants.
    """
    campo = LinkCandidatura._meta.get_field('token')

    assert campo.unique
