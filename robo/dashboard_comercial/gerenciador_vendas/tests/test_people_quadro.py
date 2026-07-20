"""
Quadro por unidade e regra de parada por vaga.

O quadro le ocupacao de dois lugares (Colaborador ativo do DP, Candidato em
processo do R&S) e nunca guarda contagem em coluna. Estes testes garantem que a
conta bate com o que existe, e que a regra de parada avisa sem bloquear.
"""
import secrets

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people import estados_recrutamento as estados_rs
from apps.people.models import (
    Cargo, Candidato, Colaborador, QuadroUnidade, Unidade, Vaga,
)
from apps.people.models_recrutamento import JUSTIFICATIVA_AUMENTO
from apps.people.services.pipeline import dar_saida, garantir_etapa_inicial
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
                                   justificativa=JUSTIFICATIVA_AUMENTO,
                                   limite_aprovados=2)
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo, 'vaga': vaga}


def _candidato(cenario, **kwargs):
    dados = {'tenant': cenario['tenant'], 'unidade': cenario['unidade'],
             'vaga': cenario['vaga'], 'nome_completo': 'Candidato',
             'whatsapp': ''.join(str(secrets.randbelow(10)) for _ in range(11))}
    dados.update(kwargs)
    return Candidato.all_tenants.create(**dados)


def _cliente(cenario, funcionalidades=('people.ver', 'people.gerir_vagas')):
    user = User.objects.create_user(username='rh_quadro', password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'],
                                            nome='Perfil quadro')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    cliente = Client()
    cliente.force_login(user)
    return cliente


# ── situacao() do quadro ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_quadro_vazio_mostra_tudo_faltando(cenario):
    quadro = QuadroUnidade.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], quadro_definido=8)

    s = quadro.situacao()
    assert s['definido'] == 8
    assert s['ativos'] == 0
    assert s['faltam'] == 8


@pytest.mark.django_db
def test_ativos_conta_colaborador_do_dp(cenario):
    """
    Le do DP, nao do Candidato: quem ja e da casa ocupa o quadro de verdade.
    """
    from apps.people import estados as estados_dp

    Colaborador.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Ja Trabalha', cargo=cenario['cargo'],
        situacao=estados_dp.SITUACAO_EFETIVADO)

    quadro = QuadroUnidade.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], quadro_definido=8)

    s = quadro.situacao()
    assert s['ativos'] == 1
    assert s['faltam'] == 7


@pytest.mark.django_db
def test_em_processo_conta_candidato_no_pipeline(cenario):
    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)

    quadro = QuadroUnidade.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], quadro_definido=8)

    assert quadro.situacao()['em_processo'] == 1


@pytest.mark.django_db
def test_quem_saiu_do_pipeline_nao_conta_em_processo(cenario):
    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)
    dar_saida(candidato, estados_rs.SAIDA_INAPTO, motivo='Não compareceu')

    quadro = QuadroUnidade.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], quadro_definido=8)

    assert quadro.situacao()['em_processo'] == 0


@pytest.mark.django_db
def test_cobre_a_falta_quando_ha_processo_suficiente(cenario):
    for _ in range(3):
        garantir_etapa_inicial(_candidato(cenario))

    quadro = QuadroUnidade.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], quadro_definido=2)

    s = quadro.situacao()
    assert s['faltam'] == 2
    assert s['cobre_a_falta'] is True   # 3 em processo cobrem os 2 que faltam


# ── Regra de parada ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_vaga_nao_atingiu_limite_com_zero_admitidos(cenario):
    assert cenario['vaga'].atingiu_limite is False


@pytest.mark.django_db
def test_vaga_atinge_limite_ao_admitir_o_teto(cenario):
    """limite_aprovados=2: dois admitidos batem o teto."""
    for _ in range(2):
        c = _candidato(cenario)
        garantir_etapa_inicial(c)
        dar_saida(c, estados_rs.SAIDA_ADMITIDO, motivo='Aprovado')

    cenario['vaga'].refresh_from_db()
    assert cenario['vaga'].total_admitidos == 2
    assert cenario['vaga'].atingiu_limite is True


@pytest.mark.django_db
def test_admitir_alem_do_limite_e_permitido_porem_avisa(cenario):
    """
    A regra de parada avisa, nao bloqueia: a decisao de admitir o 3o e do RH.
    """
    import json

    cliente = _cliente(cenario)
    admitidos = []
    for _ in range(2):
        c = _candidato(cenario)
        garantir_etapa_inicial(c)
        dar_saida(c, estados_rs.SAIDA_ADMITIDO, motivo='Aprovado')
        admitidos.append(c)

    # Terceiro, alem do teto de 2
    terceiro = _candidato(cenario)
    garantir_etapa_inicial(terceiro)
    resposta = cliente.post(
        reverse('people:pipeline_saida', args=[terceiro.pk]),
        data=json.dumps({'saida': estados_rs.SAIDA_ADMITIDO, 'motivo': 'Extra'}),
        content_type='application/json')

    corpo = resposta.json()
    assert resposta.status_code == 200        # permitido
    assert corpo['ok'] is True
    assert 'limite' in corpo['aviso'].lower()  # porem avisado
    terceiro.refresh_from_db()
    assert terceiro.saida == estados_rs.SAIDA_ADMITIDO


# ── Views ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_tela_do_quadro_renderiza(cenario):
    QuadroUnidade.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], quadro_definido=5)

    resposta = _cliente(cenario).get(reverse('people:quadro_lista'))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert 'Atendente' in corpo
    assert 'Loja Centro' in corpo


@pytest.mark.django_db
def test_salvar_quadro_pela_tela(cenario):
    resposta = _cliente(cenario).post(reverse('people:quadro_salvar'), {
        'unidade': cenario['unidade'].pk,
        'cargo': cenario['cargo'].pk,
        'quadro_definido': 6,
    })

    assert resposta.status_code == 302
    quadro = QuadroUnidade.all_tenants.get(tenant=cenario['tenant'])
    assert quadro.quadro_definido == 6


@pytest.mark.django_db
def test_quadro_duplicado_de_unidade_e_cargo_e_recusado(cenario):
    QuadroUnidade.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], quadro_definido=5)

    resposta = _cliente(cenario).post(reverse('people:quadro_salvar'), {
        'unidade': cenario['unidade'].pk,
        'cargo': cenario['cargo'].pk,
        'quadro_definido': 9,
    }, follow=True)

    assert QuadroUnidade.all_tenants.filter(tenant=cenario['tenant']).count() == 1
    assert 'já existe' in resposta.content.decode().lower()


@pytest.mark.django_db
def test_o_banco_recusa_quadro_duplicado(cenario):
    """A constraint e a garantia; o form e a cortesia."""
    from django.db import IntegrityError, transaction

    QuadroUnidade.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        cargo=cenario['cargo'], quadro_definido=5)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            QuadroUnidade.all_tenants.create(
                tenant=cenario['tenant'], unidade=cenario['unidade'],
                cargo=cenario['cargo'], quadro_definido=9)


@pytest.mark.django_db
def test_quadro_nao_vaza_entre_tenants(cenario):
    outro = TenantFactory(modulo_people=True)
    outra_unidade = Unidade.all_tenants.create(tenant=outro, nome='Deles',
                                               codigo='deles')
    outro_cargo = Cargo.all_tenants.create(tenant=outro, nome='Atendente')
    QuadroUnidade.all_tenants.create(tenant=outro, unidade=outra_unidade,
                                     cargo=outro_cargo, quadro_definido=3)
    QuadroUnidade.all_tenants.create(tenant=cenario['tenant'],
                                     unidade=cenario['unidade'],
                                     cargo=cenario['cargo'], quadro_definido=5)

    do_primeiro = _cliente(cenario).get(reverse('people:quadro_lista'))
    assert do_primeiro.content.decode().count('Loja Centro') >= 1
    assert 'Deles' not in do_primeiro.content.decode()
