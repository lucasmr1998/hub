"""
Testes do link publico de auto cadastro (gestao interna).

O que este arquivo protege: a rotacao. "Novo link" e a acao que se usa quando o
link vazou pra fora da loja, e ela so tem valor se o antigo realmente parar de
funcionar. Um bug ali seria invisivel na tela (o cartao mostraria o link novo) e
deixaria o vazamento aberto.

A view publica em si vem no passo seguinte.
"""
import pytest
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from apps.people.models import LinkCadastroUnidade, SubmissaoLinkCadastro, Unidade
from apps.people.services import (
    criar_link, desativar_link, link_ativo, links_ativos, registrar_submissao,
    resolver_por_token, rotacionar_link,
)
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


TODAS = ['people.ver', 'people.gerir_links']


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


# ──────────────────────────────────────────────
# Criar
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cria_link_com_token_forte(cenario):
    link = criar_link(cenario['unidade'])
    assert link.ativo is True
    assert len(link.token) >= 40  # token_urlsafe(32)
    assert link.caminho_publico == f'/people/publico/{link.token}/'


@pytest.mark.django_db
def test_tokens_nao_se_repetem(cenario):
    outra = Unidade.all_tenants.create(
        tenant=cenario['tenant'], nome='Loja Norte', codigo='loja-norte')
    assert criar_link(cenario['unidade']).token != criar_link(outra).token


@pytest.mark.django_db
def test_uma_unidade_pode_ter_varios_links_ativos(cenario):
    """
    E o comportamento do produto real, conferido em print: a mesma loja aparece
    com varios links vivos, um por campanha ou por turno. A primeira versao
    daqui tinha uma constraint de um ativo por unidade, que era invencao nossa.
    """
    primeiro = criar_link(cenario['unidade'], nome='Mutirao de julho')
    segundo = criar_link(cenario['unidade'], nome='Turno da noite')

    assert primeiro.pk != segundo.pk
    assert links_ativos(cenario['unidade']).count() == 2


@pytest.mark.django_db
def test_token_e_unico_globalmente(cenario):
    """
    O token e o que resolve o tenant na URL publica, que nao carrega tenant
    nenhum. Colisao ali entregaria o cadastro pra empresa errada.
    """
    link = criar_link(cenario['unidade'])
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LinkCadastroUnidade.all_tenants.create(
                tenant=cenario['tenant'], unidade=cenario['unidade'], token=link.token)


@pytest.mark.django_db
def test_link_expira_conforme_a_configuracao(cenario):
    from apps.people.models import ConfiguracaoPeople

    config = ConfiguracaoPeople.get_config(cenario['tenant'])
    config.link_expira_em_dias = 7
    config.save()

    link = criar_link(cenario['unidade'])
    assert link.expira_em is not None
    assert link.expira_em > timezone.now()


# ──────────────────────────────────────────────
# Rotacao: o antigo precisa MORRER
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_rotacionar_invalida_o_antigo(cenario):
    """
    O ponto do "Novo link". Se o antigo continuasse valendo, a acao nao serviria
    pra nada justamente no caso que a motiva: link vazado.
    """
    antigo = criar_link(cenario['unidade'])
    novo = rotacionar_link(antigo)

    antigo.refresh_from_db()
    assert antigo.ativo is False
    assert antigo.desativado_em is not None
    assert antigo.esta_valido() is False
    assert novo.esta_valido() is True
    assert novo.token != antigo.token


@pytest.mark.django_db
def test_rotacao_guarda_a_linhagem(cenario):
    """Saber de qual link o atual nasceu e parte de investigar um vazamento."""
    antigo = criar_link(cenario['unidade'])
    novo = rotacionar_link(antigo)
    assert novo.rotacionado_de_id == antigo.pk


@pytest.mark.django_db
def test_rotacionar_nao_derruba_os_outros_links_da_loja(cenario):
    """
    A diferenca em relacao a desativar tudo: rotacionar age sobre UM link, que e
    o que vazou. Os outros continuam circulando.
    """
    vazado = criar_link(cenario['unidade'], nome='Vazado')
    outro = criar_link(cenario['unidade'], nome='Intacto')

    rotacionar_link(vazado)

    outro.refresh_from_db()
    assert outro.ativo is True
    assert links_ativos(cenario['unidade']).count() == 2


@pytest.mark.django_db
def test_link_desativado_continua_existindo(cenario):
    """A trilha de submissoes aponta pra ele: apagar perderia a auditoria."""
    link = criar_link(cenario['unidade'])
    desativar_link(link)
    assert LinkCadastroUnidade.all_tenants.filter(pk=link.pk).exists()
    assert link_ativo(cenario['unidade']) is None


# ──────────────────────────────────────────────
# Validade
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_link_expirado_nao_vale(cenario):
    link = criar_link(cenario['unidade'])
    link.expira_em = timezone.now() - timedelta(minutes=1)
    link.save()
    assert link.esta_valido() is False


@pytest.mark.django_db
def test_link_no_teto_de_submissoes_nao_vale(cenario):
    link = criar_link(cenario['unidade'], max_submissoes=2)
    link.submissoes = 2
    link.save()
    assert link.esta_valido() is False


@pytest.mark.django_db
def test_link_se_desativa_ao_bater_o_teto(cenario):
    link = criar_link(cenario['unidade'], max_submissoes=1)
    registrar_submissao(link, resultado='criado')

    link.refresh_from_db()
    assert link.submissoes == 1
    assert link.ativo is False


@pytest.mark.django_db
def test_rejeicao_nao_conta_no_teto(cenario):
    """Senao um robo derrubaria o link da loja so mandando lixo."""
    link = criar_link(cenario['unidade'], max_submissoes=2)
    registrar_submissao(link, resultado='rejeitado', erro='honeypot')

    link.refresh_from_db()
    assert link.submissoes == 0
    assert link.ativo is True


# ──────────────────────────────────────────────
# Resolucao por token e trilha
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_resolve_por_token_sem_usuario_logado(cenario):
    """
    A view publica nao tem usuario, entao o TenantManager nao filtra nada. E
    este link que diz de qual tenant e o cadastro.
    """
    link = criar_link(cenario['unidade'])
    achado = resolver_por_token(link.token)
    assert achado.pk == link.pk
    assert achado.tenant_id == cenario['tenant'].pk


@pytest.mark.django_db
def test_token_inexistente_resolve_pra_nada(cenario):
    assert resolver_por_token('nao-existe') is None
    assert resolver_por_token('') is None
    assert resolver_por_token(None) is None


@pytest.mark.django_db
def test_submissao_guarda_cpf_mascarado(cenario):
    """
    A pessoa ja esta no Colaborador. Guardar documento inteiro em duas tabelas
    so aumenta a superficie de vazamento sem ganhar nada.
    """
    link = criar_link(cenario['unidade'])
    registrar_submissao(link, resultado='criado',
                        dados={'cpf': '52998224725', 'nome_completo': 'Maria'})

    submissao = SubmissaoLinkCadastro.all_tenants.filter(link=link).first()
    assert '52998224725' not in str(submissao.payload)
    assert submissao.payload['nome_completo'] == 'Maria'


@pytest.mark.django_db
def test_submissao_conta_e_marca_o_horario(cenario):
    link = criar_link(cenario['unidade'])
    registrar_submissao(link, resultado='criado')

    link.refresh_from_db()
    assert link.submissoes == 1
    assert link.ultima_submissao_em is not None


# ──────────────────────────────────────────────
# Tela
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_tela_lista_os_links(cenario):
    criar_link(cenario['unidade'], nome='Um')
    criar_link(cenario['unidade'], nome='Dois')
    resposta = _cliente(cenario['tenant']).get('/people/links/')

    assert resposta.status_code == 200
    assert len(resposta.context['links']) == 2


@pytest.mark.django_db
def test_tela_mostra_a_url_completa(cenario):
    link = criar_link(cenario['unidade'])
    corpo = _cliente(cenario['tenant']).get('/people/links/').content.decode()
    assert link.token in corpo


@pytest.mark.django_db
def test_filtra_por_unidade(cenario):
    outra = Unidade.all_tenants.create(
        tenant=cenario['tenant'], nome='Loja Norte', codigo='loja-norte')
    criar_link(cenario['unidade'], nome='Do Centro')
    criar_link(outra, nome='Do Norte')

    corpo = _cliente(cenario['tenant']).get(
        f'/people/links/?unidade={cenario["unidade"].pk}').content.decode()
    assert 'Do Centro' in corpo
    assert 'Do Norte' not in corpo


@pytest.mark.django_db
def test_cria_pela_tela(cenario):
    cliente = _cliente(cenario['tenant'])
    cliente.post('/people/links/novo/', {
        'unidade': cenario['unidade'].pk, 'nome': 'Mutirao'})
    link = link_ativo(cenario['unidade'])
    assert link is not None
    assert link.nome == 'Mutirao'



@pytest.mark.django_db
def test_rotaciona_pela_tela(cenario):
    antigo = criar_link(cenario['unidade'])
    cliente = _cliente(cenario['tenant'])

    cliente.post(f'/people/links/{antigo.pk}/rotacionar/')

    antigo.refresh_from_db()
    assert antigo.ativo is False
    assert link_ativo(cenario['unidade']).token != antigo.token


@pytest.mark.django_db
def test_desativa_e_reativa_pela_tela(cenario):
    link = criar_link(cenario['unidade'])
    cliente = _cliente(cenario['tenant'])

    cliente.post(f'/people/links/{link.pk}/alternar-ativo/')
    assert link_ativo(cenario['unidade']) is None

    cliente.post(f'/people/links/{link.pk}/alternar-ativo/')
    assert link_ativo(cenario['unidade']) is not None


@pytest.mark.django_db
def test_acoes_so_aceitam_post(cenario):
    link = criar_link(cenario['unidade'])
    cliente = _cliente(cenario['tenant'])
    assert cliente.get('/people/links/novo/').status_code == 405
    for acao in ['rotacionar', 'alternar-ativo']:
        resposta = cliente.get(f'/people/links/{link.pk}/{acao}/')
        assert resposta.status_code == 405, acao


@pytest.mark.django_db
def test_quem_so_ve_nao_gerencia(cenario):
    link = criar_link(cenario['unidade'])
    cliente = _cliente(cenario['tenant'], 'leitora', funcionalidades=['people.ver'])

    assert cliente.post(f'/people/links/{link.pk}/rotacionar/').status_code == 403
    corpo = cliente.get('/people/links/').content.decode()
    assert 'Novo link' not in corpo


@pytest.mark.django_db
def test_nao_cria_link_em_unidade_de_outro_tenant(cenario):
    outro = TenantFactory(modulo_people=True)
    alheia = Unidade.all_tenants.create(tenant=outro, nome='Alheia', codigo='alheia')
    cliente = _cliente(cenario['tenant'])

    assert cliente.post('/people/links/novo/', {'unidade': alheia.pk}).status_code == 404


@pytest.mark.django_db
def test_nao_rotaciona_link_de_outro_tenant(cenario):
    outro = TenantFactory(modulo_people=True)
    alheia = Unidade.all_tenants.create(tenant=outro, nome='Alheia', codigo='alheia')
    link_alheio = criar_link(alheia)
    cliente = _cliente(cenario['tenant'])

    assert cliente.post(f'/people/links/{link_alheio.pk}/rotacionar/').status_code == 404


@pytest.mark.django_db
def test_qr_do_link_e_svg(cenario):
    """SVG e nao PNG: o uso real e cartaz na parede e precisa escalar."""
    link = criar_link(cenario['unidade'])
    resposta = _cliente(cenario['tenant']).get(f'/people/links/{link.pk}/qr.svg')

    assert resposta.status_code == 200
    assert resposta['Content-Type'] == 'image/svg+xml'
    assert b'<svg' in resposta.content
    assert 'attachment' in resposta['Content-Disposition']


@pytest.mark.django_db
def test_tela_nao_mostra_link_de_outro_tenant(cenario):
    outro = TenantFactory(modulo_people=True)
    alheia = Unidade.all_tenants.create(tenant=outro, nome='Alheia', codigo='alheia')
    link_alheio = criar_link(alheia)
    criar_link(cenario['unidade'])

    corpo = _cliente(cenario['tenant']).get('/people/links/').content.decode()
    assert link_alheio.token not in corpo
    assert 'Alheia' not in corpo
