"""
Curriculo em storage privado.

Curriculo e dado pessoal denso. MEDIA_ROOT e servido pela rota aberta `/media/`
sem autenticacao, entao o arquivo NAO pode morar la. Estes testes defendem as
tres coisas que importam: fica fora de MEDIA_ROOT, so sai por view autenticada,
e nao cruza tenant.
"""
import secrets

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.people.models import Cargo, Candidato, Unidade, Vaga
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
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo, 'vaga': vaga}


def _candidato(cenario, tenant=None, unidade=None, com_arquivo=True):
    cv = SimpleUploadedFile('cv.pdf', b'%PDF-1.4 conteudo sigiloso',
                            content_type='application/pdf') if com_arquivo else None
    return Candidato.all_tenants.create(
        tenant=tenant or cenario['tenant'],
        unidade=unidade or cenario['unidade'],
        nome_completo='Maria Candidata',
        whatsapp=''.join(str(secrets.randbelow(10)) for _ in range(11)),
        curriculo=cv)


def _cliente(cenario, username='rh_cv', tenant=None,
             funcionalidades=('people.ver', 'people.gerir_vagas')):
    alvo = tenant or cenario['tenant']
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=alvo)
    perfil = PerfilPermissao.objects.create(tenant=alvo, nome=f'P {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=alvo, perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


# ── O arquivo nao pode estar em MEDIA_ROOT ───────────────────────────────────

@pytest.mark.django_db
def test_curriculo_fica_fora_da_pasta_media_servida(cenario):
    """
    O teste central. A rota aberta `/media/` serve o diretorio de midia sem
    login nenhum, entao o curriculo nao pode estar dentro dele.

    Compara contra `BASE_DIR/'media'`, que e a formula do settings de PRODUCAO,
    e nao contra `settings.MEDIA_ROOT`: em dev o settings_local aponta o
    MEDIA_ROOT pra RAIZ DO REPO (pra servir anexo do workspace), entao ali tudo
    e "dentro" e a asserção nao diria nada. O que precisa valer em prod e que
    `/app/private_media` nao esta sob `/app/media`.
    """
    candidato = _candidato(cenario)

    caminho = candidato.curriculo.path
    pasta_media_de_prod = str(settings.BASE_DIR / 'media')

    assert not caminho.startswith(pasta_media_de_prod), (
        f'Curriculo dentro da pasta servida por /media/ ({caminho}): '
        f'seria baixavel sem autenticacao.')
    assert 'private_media' in caminho


@pytest.mark.django_db
def test_storage_do_campo_e_o_privado(cenario):
    """Guarda contra alguem trocar o storage de volta sem perceber."""
    from apps.people.models_recrutamento import PrivateCurriculoStorage

    campo = Candidato._meta.get_field('curriculo')
    assert isinstance(campo.storage, PrivateCurriculoStorage)


# ── So sai por view autenticada ──────────────────────────────────────────────

@pytest.mark.django_db
def test_anonimo_nao_baixa_curriculo(cenario):
    candidato = _candidato(cenario)

    resposta = Client().get(
        reverse('people:candidato_curriculo', args=[candidato.pk]))

    assert resposta.status_code in (302, 403)  # redireciona pro login ou nega


@pytest.mark.django_db
def test_rh_autenticado_baixa(cenario):
    candidato = _candidato(cenario)

    resposta = _cliente(cenario).get(
        reverse('people:candidato_curriculo', args=[candidato.pk]))

    assert resposta.status_code == 200
    assert resposta['Content-Type'] == 'application/pdf'
    assert b'conteudo sigiloso' in b''.join(resposta.streaming_content)


@pytest.mark.django_db
def test_candidato_sem_curriculo_da_404(cenario):
    candidato = _candidato(cenario, com_arquivo=False)

    resposta = _cliente(cenario).get(
        reverse('people:candidato_curriculo', args=[candidato.pk]))

    assert resposta.status_code == 404


@pytest.mark.django_db
def test_anonimizado_nao_entrega_curriculo(cenario):
    """
    Depois do expurgo LGPD o arquivo foi apagado. A rota nao pode estourar 500
    tentando abrir o que nao existe mais.
    """
    candidato = _candidato(cenario)
    candidato.anonimizar()

    resposta = _cliente(cenario).get(
        reverse('people:candidato_curriculo', args=[candidato.pk]))

    assert resposta.status_code == 404


# ── Nao cruza tenant ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_curriculo_de_outro_tenant_da_404(cenario):
    """
    O pk e sequencial e adivinhavel. Sem o escopo de tenant, o RH de uma
    empresa baixaria o curriculo de candidato de outra.
    """
    outro = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=outro, nome_empresa=outro.nome,
                                           ativo=True)
    unidade_alheia = Unidade.all_tenants.create(tenant=outro, nome='Deles',
                                                codigo='deles')
    alheio = _candidato(cenario, tenant=outro, unidade=unidade_alheia)

    resposta = _cliente(cenario).get(
        reverse('people:candidato_curriculo', args=[alheio.pk]))

    assert resposta.status_code == 404


@pytest.mark.django_db
def test_quem_nao_tem_permissao_de_people_nao_baixa(cenario):
    candidato = _candidato(cenario)
    cliente = _cliente(cenario, username='sem_perm', funcionalidades=())

    resposta = cliente.get(
        reverse('people:candidato_curriculo', args=[candidato.pk]))

    assert resposta.status_code == 403
