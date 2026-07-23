"""
Tela de configuracao do fluxo (gap 3 dos prints).

Sem ela o cliente ficava preso nas seis etapas do seed, o que e o mesmo que ter
etapa em codigo, contrariando o desenho "etapa e dado, saida e codigo".

O que estes testes defendem: a edicao respeita escopo (tenant e unidade), e as
duas guardas que impedem perda de dado (nao apagar etapa com gente dentro, nao
resetar fluxo com gente no meio).
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people.models import Candidato, Cargo, EtapaPipeline, Unidade
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)   # signal semeia as 7 etapas
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    return {'tenant': tenant, 'unidade': unidade}


def _cliente(cenario, username='rh_fluxo',
             funcionalidades=('people.ver', 'people.gerir_vagas')):
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'],
                                            nome=f'P {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


def _candidato(cenario, etapa, nome='Alguem'):
    import secrets
    return Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo=nome, etapa=etapa,
        whatsapp=''.join(str(secrets.randbelow(10)) for _ in range(11)))


# ── Render ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_tela_lista_as_etapas_do_fluxo(cenario):
    corpo = _cliente(cenario).get(reverse('people:fluxo_config')).content.decode()

    assert 'Análise de inscrição' in corpo
    assert 'Admissão' in corpo
    # As saidas aparecem, marcadas como fixas
    assert 'Banco de talentos' in corpo


@pytest.mark.django_db
def test_tela_mostra_etapa_desativada_em_vez_de_esconder(cenario):
    etapa = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'], nome='Análise de inscrição')
    etapa.ativa = False
    etapa.save()

    corpo = _cliente(cenario).get(reverse('people:fluxo_config')).content.decode()

    assert 'Análise de inscrição' in corpo
    assert 'Desativada' in corpo


# ── Criar, editar, ordenar ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_criar_etapa_entra_no_fim_do_fluxo(cenario):
    _cliente(cenario).post(reverse('people:fluxo_etapa_salvar'), {
        'nome': 'Entrevista com RH', 'cor': 'roxo', 'sla_dias': '4'})

    nova = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                         nome='Entrevista com RH')
    assert nova.ordem == 7      # as seis padrao mais esta
    assert nova.sla_dias == 4
    assert nova.cor == 'roxo'
    assert nova.ativa


@pytest.mark.django_db
def test_nome_duplicado_no_mesmo_fluxo_e_recusado(cenario):
    """A unique do banco barraria, mas com IntegrityError na cara do usuario."""
    resposta = _cliente(cenario).post(reverse('people:fluxo_etapa_salvar'),
                                      {'nome': 'análise de inscrição'}, follow=True)

    assert 'Já existe' in resposta.content.decode()
    assert EtapaPipeline.all_tenants.filter(
        tenant=cenario['tenant'], nome__iexact='análise de inscrição').count() == 1


@pytest.mark.django_db
def test_editar_etapa_pelo_mesmo_formulario(cenario):
    etapa = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'], nome='Análise de inscrição')

    _cliente(cenario).post(reverse('people:fluxo_etapa_salvar'), {
        'pk': etapa.pk, 'nome': 'Análise de inscrição', 'cor': 'azul',
        'sla_dias': '2'})

    etapa.refresh_from_db()
    assert etapa.nome == 'Análise de inscrição'
    assert etapa.sla_dias == 2


@pytest.mark.django_db
def test_mover_troca_a_ordem_com_a_vizinha(cenario):
    etapas = list(EtapaPipeline.do_escopo(cenario['tenant']).order_by('ordem'))
    segunda = etapas[1]

    _cliente(cenario).post(reverse('people:fluxo_etapa_mover', args=[segunda.pk]),
                           {'direcao': 'cima'})

    nova_ordem = [e.nome for e in
                  EtapaPipeline.do_escopo(cenario['tenant']).order_by('ordem')]
    assert nova_ordem[0] == segunda.nome


@pytest.mark.django_db
def test_mover_a_primeira_pra_cima_nao_quebra(cenario):
    """Nao ha vizinha acima. Deve ser no-op, nao erro."""
    primeira = EtapaPipeline.do_escopo(cenario['tenant']).order_by('ordem').first()

    resposta = _cliente(cenario).post(
        reverse('people:fluxo_etapa_mover', args=[primeira.pk]), {'direcao': 'cima'})

    assert resposta.status_code == 302
    assert EtapaPipeline.do_escopo(cenario['tenant']).order_by('ordem').first().pk == primeira.pk


# ── As guardas que evitam perda de dado ──────────────────────────────────────

@pytest.mark.django_db
def test_nao_apaga_etapa_com_candidato_dentro(cenario):
    """
    Apagar deixaria o candidato orfao no board. Pra tirar de circulacao com
    gente dentro, o caminho e desativar.
    """
    etapa = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'], nome='Análise de inscrição')
    _candidato(cenario, etapa)

    resposta = _cliente(cenario).post(
        reverse('people:fluxo_etapa_remover', args=[etapa.pk]), follow=True)

    assert EtapaPipeline.all_tenants.filter(pk=etapa.pk).exists()
    assert 'desative' in resposta.content.decode().lower()


@pytest.mark.django_db
def test_apaga_etapa_vazia(cenario):
    etapa = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                          nome='Perfil comportamental')

    _cliente(cenario).post(reverse('people:fluxo_etapa_remover', args=[etapa.pk]))

    assert not EtapaPipeline.all_tenants.filter(pk=etapa.pk).exists()


@pytest.mark.django_db
def test_desativar_nao_apaga_e_preserva_o_candidato(cenario):
    etapa = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'], nome='Análise de inscrição')
    candidato = _candidato(cenario, etapa)

    _cliente(cenario).post(reverse('people:fluxo_etapa_alternar', args=[etapa.pk]))

    etapa.refresh_from_db()
    candidato.refresh_from_db()
    assert not etapa.ativa
    assert candidato.etapa_id == etapa.pk   # continua apontando, nao ficou orfao


@pytest.mark.django_db
def test_nao_reseta_fluxo_com_candidato_no_meio(cenario):
    """Resetar com gente dentro deixaria todos fora de etapa de uma vez."""
    etapa = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'], nome='Análise de inscrição')
    _candidato(cenario, etapa)

    resposta = _cliente(cenario).post(reverse('people:fluxo_resetar'), follow=True)

    assert EtapaPipeline.all_tenants.filter(pk=etapa.pk).exists()
    assert 'fora de etapa' in resposta.content.decode().lower()


@pytest.mark.django_db
def test_resetar_fluxo_vazio_volta_as_seis(cenario):
    EtapaPipeline.all_tenants.filter(tenant=cenario['tenant']).delete()

    _cliente(cenario).post(reverse('people:fluxo_resetar'))

    assert EtapaPipeline.do_escopo(cenario['tenant']).count() == 6


# ── Escopo ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_etapa_criada_com_unidade_vale_so_pra_ela(cenario):
    """
    Criar a primeira etapa da unidade faz ela parar de herdar o fluxo do tenant.
    """
    _cliente(cenario).post(reverse('people:fluxo_etapa_salvar'), {
        'unidade': cenario['unidade'].pk, 'nome': 'Entrevista na loja'})

    do_tenant = EtapaPipeline.do_escopo(cenario['tenant'])
    da_unidade = EtapaPipeline.do_escopo(cenario['tenant'], cenario['unidade'])

    assert do_tenant.count() == 6
    assert [e.nome for e in da_unidade] == ['Entrevista na loja']


@pytest.mark.django_db
def test_nao_edita_etapa_de_outro_tenant(cenario):
    outro = TenantFactory(modulo_people=True)
    alheia = EtapaPipeline.do_escopo(outro).first()

    resposta = _cliente(cenario).post(reverse('people:fluxo_etapa_salvar'),
                                      {'pk': alheia.pk, 'nome': 'Sequestrada'})

    alheia.refresh_from_db()
    assert resposta.status_code == 404
    assert alheia.nome != 'Sequestrada'


@pytest.mark.django_db
def test_quem_so_ve_nao_configura(cenario):
    cliente = _cliente(cenario, username='so_ve', funcionalidades=('people.ver',))

    assert cliente.get(reverse('people:fluxo_config')).status_code == 200
    assert cliente.post(reverse('people:fluxo_etapa_salvar'),
                        {'nome': 'X'}).status_code == 403


# ── Hub de Configuracoes: as tres telas viraram abas ─────────────────────────

@pytest.mark.django_db
def test_hub_renderiza_as_cinco_abas(cenario):
    """
    Etapas, Mensagens, Quadro, Campos e Captacao numa pagina so. As abas sao
    client-side, entao os cinco paineis vem no HTML; o JS mostra um por vez.
    """
    corpo = _cliente(cenario).get(reverse('people:fluxo_config')).content.decode()

    for aba in ['etapas', 'mensagens', 'quadro', 'campos', 'captacao']:
        assert f'data-tab="{aba}"' in corpo
        assert f'class="config-painel" id="{aba}"' in corpo
    # Criar/editar etapa, campo e quadro acontecem em modal, e nao mais inline.
    for modal in ['modal-etapa', 'modal-campo', 'modal-quadro']:
        assert f'id="{modal}"' in corpo


@pytest.mark.django_db
def test_tab_invalido_cai_na_primeira_aba(cenario):
    """`?tab=` forjado nao pode deixar dois paineis abertos nem nenhum."""
    corpo = _cliente(cenario).get(
        reverse('people:fluxo_config'), {'tab': 'inexistente'}).content.decode()

    # Etapas ativa (sem hidden); as demais escondidas.
    assert 'id="etapas" hidden' not in corpo
    for aba in ['mensagens', 'quadro', 'campos', 'captacao']:
        assert f'id="{aba}" hidden' in corpo


@pytest.mark.django_db
def test_rotas_antigas_redirecionam_pro_hub(cenario):
    """Fluxo, Campos e Captacao eram URLs proprias; agora levam ao hub na aba."""
    cliente = _cliente(cenario)

    r_campos = cliente.get(reverse('people:campos_config'))
    assert r_campos.status_code == 302 and r_campos['Location'].endswith('tab=campos')

    r_capt = cliente.get(reverse('people:banco_talentos_links'))
    assert r_capt.status_code == 302 and r_capt['Location'].endswith('tab=captacao')

    r_quadro = cliente.get(reverse('people:quadro_lista'))
    assert r_quadro.status_code == 302 and r_quadro['Location'].endswith('tab=quadro')


@pytest.mark.django_db
def test_salvar_mensagem_volta_pra_aba_mensagens(cenario):
    """
    Sem o ?tab, salvar uma mensagem devolveria o RH pra aba Etapas, e ele leria
    isso como "cade o que eu salvei".
    """
    etapa = EtapaPipeline.objects.filter(tenant=cenario['tenant']).first()
    resposta = _cliente(cenario).post(reverse('people:fluxo_mensagem_salvar'),
                                      {'etapa': etapa.pk, 'texto': 'Oi {{primeiro_nome}}'})

    assert resposta.status_code == 302
    assert resposta['Location'].endswith('tab=mensagens')
