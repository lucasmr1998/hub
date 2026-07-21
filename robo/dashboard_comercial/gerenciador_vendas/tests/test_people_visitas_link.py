"""
Tarefa 216: visitas por link, pra tela mostrar taxa de conversao.

A tela dizia quantas candidaturas cada link trouxe e nao quantas pessoas
abriram. Sem o denominador nao da pra saber qual canal converte: 200 visitas
com 2 candidaturas e pior que 30 com 8, e so a taxa mostra isso.

DUAS ARMADILHAS, e os testes existem por causa delas:

1. WhatsApp e Facebook BUSCAM a URL pra montar o preview quando alguem cola o
   link. O ato de divulgar ja geraria "visita", e os dois canais em uso sao
   exatamente esses. Contar robo inverteria a leitura da tela.

2. Contar ACESSO em vez de VISITANTE deixaria numerador e denominador em
   unidades diferentes. Recarregar a pagina, ou voltar pra corrigir um campo,
   e comum num formulario.
"""
import secrets

import pytest
from django.test import Client
from django.utils import timezone

from apps.people.models import Cargo, LinkCandidatura, Unidade, Vaga
from apps.people.utils import e_robo
from apps.sistema.models import ConfiguracaoEmpresa
from tests.factories import TenantFactory

NAVEGADOR = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
             'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari')


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   status='publicada')
    link = LinkCandidatura.all_tenants.create(
        tenant=tenant, vaga=vaga, unidade=unidade, canal='instagram',
        token=secrets.token_urlsafe(16))
    return {'tenant': tenant, 'unidade': unidade, 'vaga': vaga, 'link': link}


def _abrir(cenario, cliente=None, agente=NAVEGADOR):
    cliente = cliente or Client()
    return cliente.get(f'/people/candidatura/{cenario["link"].token}/',
                       HTTP_USER_AGENT=agente)


def _visitas(cenario):
    cenario['link'].refresh_from_db()
    return cenario['link'].visitas


# ── Contagem por visitante, nao por acesso ───────────────────────────────────

@pytest.mark.django_db
def test_primeira_visita_conta(cenario):
    _abrir(cenario)

    assert _visitas(cenario) == 1


@pytest.mark.django_db
def test_recarregar_nao_conta_de_novo(cenario):
    """
    O mesmo visitante recarregando nao e visitante novo. Num formulario, voltar
    pra corrigir um campo e comum, e contaria varias vezes a mesma pessoa.
    """
    cliente = Client()
    _abrir(cenario, cliente)
    _abrir(cenario, cliente)
    _abrir(cenario, cliente)

    assert _visitas(cenario) == 1


@pytest.mark.django_db
def test_visitantes_diferentes_contam_separado(cenario):
    _abrir(cenario, Client())
    _abrir(cenario, Client())

    assert _visitas(cenario) == 2


@pytest.mark.django_db
def test_o_cookie_e_por_link(cenario):
    """
    Quem ja visitou um link continua sendo visitante novo em outro. Cookie
    global contaria uma pessoa so uma vez no sistema inteiro e zeraria a
    atribuicao por canal, que e a razao de haver um link por canal.
    """
    outro = LinkCandidatura.all_tenants.create(
        tenant=cenario['tenant'], vaga=cenario['vaga'],
        unidade=cenario['unidade'], canal='facebook',
        token=secrets.token_urlsafe(16))

    cliente = Client()
    _abrir(cenario, cliente)
    cliente.get(f'/people/candidatura/{outro.token}/', HTTP_USER_AGENT=NAVEGADOR)

    outro.refresh_from_db()
    assert _visitas(cenario) == 1
    assert outro.visitas == 1


# ── Robo nao conta ───────────────────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('agente', [
    'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
    'WhatsApp/2.23.20.0 A',
    'Twitterbot/1.0',
    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
    'python-requests/2.31.0',
])
def test_robo_nao_conta_como_visita(cenario, agente):
    """
    Colar o link num grupo de WhatsApp faz o proprio WhatsApp buscar a URL. Sem
    este filtro, divulgar ja geraria movimento que ninguem fez.
    """
    _abrir(cenario, agente=agente)

    assert _visitas(cenario) == 0


@pytest.mark.django_db
def test_user_agent_vazio_nao_conta(cenario):
    """Navegador de verdade sempre manda User-Agent."""
    _abrir(cenario, agente='')

    assert _visitas(cenario) == 0


def test_navegador_de_verdade_nao_e_confundido_com_robo():
    """A heuristica nao pode ser tao larga que derrube gente."""
    assert e_robo(NAVEGADOR) is False
    assert e_robo('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36') is False
    assert e_robo('Mozilla/5.0 (Linux; Android 13; SM-A045M) Chrome/119') is False


# ── A taxa, e quando NAO mostrar ─────────────────────────────────────────────

@pytest.mark.django_db
def test_taxa_de_conversao(cenario):
    link = cenario['link']
    link.visitas = 40
    link.candidaturas = 10
    link.save()

    assert link.taxa_confiavel is True
    assert link.taxa_conversao == 25.0


@pytest.mark.django_db
def test_link_mais_velho_que_a_medicao_nao_mostra_taxa(cenario):
    """
    Link que ja tinha candidatura antes de a medicao comecar daria taxa acima de
    100%. Um numero que nasce quebrado destroi a confianca na tela inteira, e a
    saida e dizer desde quando esta medindo.
    """
    link = cenario['link']
    link.candidaturas = 4
    link.visitas = 0
    link.save()

    assert link.taxa_confiavel is False
    assert link.taxa_conversao is None


@pytest.mark.django_db
def test_sem_visita_ainda_nao_divide_por_zero(cenario):
    assert cenario['link'].visitas == 0
    assert cenario['link'].taxa_conversao is None


@pytest.mark.django_db
def test_link_novo_ja_nasce_medindo(cenario):
    """Sem a data, a tela nao saberia diferenciar "sem visita" de "sem medicao"."""
    assert cenario['link'].medindo_visitas_desde is not None
    assert cenario['link'].medindo_visitas_desde <= timezone.now()


@pytest.mark.django_db
def test_a_tela_mostra_a_taxa(cenario):
    from django.contrib.auth.models import User
    from django.urls import reverse

    from apps.sistema.models import (
        Funcionalidade, PerfilPermissao, PerfilUsuario, PermissaoUsuario,
    )

    link = cenario['link']
    link.visitas = 50
    link.candidaturas = 5
    link.save()

    user = User.objects.create_user(username='rh_216', password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'], nome='P216')
    for codigo in ('people.ver', 'people.gerir_vagas'):
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)

    cliente = Client()
    cliente.force_login(user)
    corpo = cliente.get(reverse('people:vaga_editar',
                                args=[cenario['vaga'].pk])).content.decode()

    assert '50 visitas' in corpo
    # Virgula, e nao ponto: o locale e pt-BR e o usuario le "10,0%".
    assert '10,0%' in corpo


# ── O que a decisao de desenho garante ───────────────────────────────────────

@pytest.mark.django_db
def test_visita_nao_cria_sessao_no_banco(cenario):
    """
    A contagem usa cookie proprio, e nao a sessao do Django, porque a sessao
    mora em tabela e o `clearsessions` nao roda em lugar nenhum do projeto. Uma
    sessao por visitante anonimo de QR faria essa virar a tabela que mais cresce
    no sistema, sem nada limpando.
    """
    from django.contrib.sessions.models import Session

    antes = Session.objects.count()
    _abrir(cenario, Client())
    _abrir(cenario, Client())

    assert Session.objects.count() == antes


@pytest.mark.django_db
def test_visita_nao_grava_dado_pessoal(cenario):
    """Quem so visitou nao consentiu com nada. O cookie so diz "ja contei"."""
    cliente = Client()
    resposta = _abrir(cenario, cliente)

    cookie = resposta.cookies.get(f'hv{cenario["link"].pk}')
    assert cookie is not None
    assert cookie.value == '1'          # nenhum identificador de pessoa
    assert cookie['httponly']
