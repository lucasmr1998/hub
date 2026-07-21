"""
A ponte entre Recrutamento e Departamento Pessoal (tarefa 218, item 13).

E o unico ponto do modulo onde um Candidato vira Colaborador. Era a ultima
lacuna estrutural do corte B: a FK `Candidato.colaborador` existia desde o
inicio, esperando quem a preenchesse.

O QUE ESTES TESTES DEFENDEM, em ordem de gravidade:

1. COPIA, E NAO VINCULO. Mudar a vaga depois da admissao nao pode alterar o que
   ficou registrado pro colaborador. E requisito trabalhista, nao preferencia:
   o que valeu na contratacao tem que continuar sendo o que valeu, mesmo que a
   vaga seja reaproveitada e editada.
2. Os dois registros COEXISTEM. O candidato nao vira colaborador nem some;
   apagar destruiria a analise de canal ("de onde vieram os que ficaram?").
3. Conflito de dedup NAO cria segunda linha. Ex-funcionario voltando ja existe
   no DP, e a R1 do modulo proibe a duplicata.
4. Nao admite duas vezes, e nao admite anonimizado.
"""
import datetime

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people import estados
from apps.people import estados_recrutamento as estados_rs
from apps.people.models import (
    Candidato, Cargo, Colaborador, EtapaPipeline, Unidade, Vaga,
)
from apps.people.services.admissao import AdmissaoInvalida, admitir_candidato
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory

HOJE = datetime.date.today()


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(
        tenant=tenant, unidade=unidade, cargo=cargo,
        titulo='Atendente noturno', tipo_contratacao='clt', status='publicada')
    etapa = EtapaPipeline.all_tenants.get(tenant=tenant, nome='Admissão')
    candidato = Candidato.all_tenants.create(
        tenant=tenant, unidade=unidade, vaga=vaga, etapa=etapa,
        nome_completo='James Dean Vieira', whatsapp='5589994395653',
        email='james@exemplo.com', cidade='Teresina', estado='PI')
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo,
            'vaga': vaga, 'etapa': etapa, 'candidato': candidato}


def _cliente(cenario, funcionalidades=('people.ver', 'people.gerir_vagas')):
    user = User.objects.create_user(username='rh_ponte', password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'], nome='P ponte')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


# ── O caminho feliz ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_admissao_cria_colaborador_e_liga_ao_candidato(cenario):
    resultado = admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                                  data_inicio=HOJE)

    assert resultado.ok
    colaborador = resultado.colaborador
    cenario['candidato'].refresh_from_db()

    assert cenario['candidato'].colaborador_id == colaborador.pk
    assert colaborador.nome_completo == 'James Dean Vieira'
    assert colaborador.unidade_id == cenario['unidade'].pk
    assert colaborador.cargo_id == cenario['cargo'].pk
    assert colaborador.data_admissao == HOJE


@pytest.mark.django_db
def test_colaborador_entra_em_admissao_e_nao_em_experiencia(cenario):
    """
    Falta CPF e documento, e e justamente isso que a fase de admissao do DP
    existe pra coletar. Entrar em experiencia pularia a coleta.
    """
    resultado = admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                                  data_inicio=HOJE)

    assert resultado.colaborador.situacao == estados.SITUACAO_EM_ADMISSAO


@pytest.mark.django_db
def test_colaborador_nasce_pendente_de_revisao_por_falta_de_cpf(cenario):
    """
    O formulario publico nao coleta CPF de proposito (atrito de conversao). O
    colaborador nasce sem, e a fila de "pendente de revisao" e o que garante que
    alguem complete.
    """
    resultado = admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                                  data_inicio=HOJE)

    assert resultado.colaborador.cpf is None
    assert resultado.colaborador.pendente_revisao is True


@pytest.mark.django_db
def test_candidato_sai_como_admitido(cenario):
    admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                      data_inicio=HOJE)

    cenario['candidato'].refresh_from_db()
    assert cenario['candidato'].saida == estados_rs.SAIDA_ADMITIDO


@pytest.mark.django_db
def test_os_dois_registros_coexistem(cenario):
    """
    O candidato NAO vira colaborador nem some. Apagar destruiria a analise de
    canal: sem ele nao da pra responder de onde vieram os que ficaram.
    """
    admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                      data_inicio=HOJE)

    assert Candidato.all_tenants.filter(pk=cenario['candidato'].pk).exists()
    assert Colaborador.all_tenants.filter(
        tenant=cenario['tenant'], nome_completo='James Dean Vieira').exists()


# ── COPIA, e nao vinculo. E o ponto da feature ───────────────────────────────

@pytest.mark.django_db
def test_mudar_a_vaga_depois_nao_altera_o_colaborador(cenario):
    """
    O TESTE MAIS IMPORTANTE DESTE ARQUIVO.

    Requisito trabalhista, nao preferencia: o que valeu na contratacao tem que
    continuar sendo o que valeu, mesmo que a vaga seja reaproveitada e editada
    pra outro processo depois.
    """
    resultado = admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                                  data_inicio=HOJE)
    colaborador = resultado.colaborador
    cargo_na_admissao = colaborador.cargo_id

    outro_cargo = Cargo.all_tenants.create(tenant=cenario['tenant'],
                                           nome='Gerente')
    cenario['vaga'].cargo = outro_cargo
    cenario['vaga'].titulo = 'Gerente de loja'
    cenario['vaga'].tipo_contratacao = 'pj'
    cenario['vaga'].save()

    colaborador.refresh_from_db()
    assert colaborador.cargo_id == cargo_na_admissao
    assert colaborador.cargo_id != outro_cargo.pk


@pytest.mark.django_db
def test_regime_da_vaga_e_copiado_quando_casa_com_a_lista(cenario):
    resultado = admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                                  data_inicio=HOJE)

    assert resultado.colaborador.regime_contratacao == 'clt'


@pytest.mark.django_db
def test_regime_em_texto_livre_nao_vira_lixo_no_campo(cenario):
    """
    `tipo_contratacao` da vaga e texto livre; o do colaborador e choices. Copiar
    sem conferir gravaria valor que outras telas filtram e nunca encontrariam.
    """
    # Cabe nos 20 caracteres do campo da vaga, e nao casa com nenhuma choice
    # do colaborador, que e o que este teste exercita.
    cenario['vaga'].tipo_contratacao = 'Estágio remunerado'
    cenario['vaga'].save()

    resultado = admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                                  data_inicio=HOJE)

    assert resultado.colaborador.regime_contratacao == ''


# ── As guardas ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_nao_admite_duas_vezes(cenario):
    admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                      data_inicio=HOJE)
    cenario['candidato'].refresh_from_db()

    with pytest.raises(AdmissaoInvalida, match='já foi enviado'):
        admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                          data_inicio=HOJE)


@pytest.mark.django_db
def test_nao_admite_candidato_anonimizado(cenario):
    """Sem nome e sem contato nao ha o que virar ficha de colaborador."""
    cenario['candidato'].anonimizar()
    cenario['candidato'].refresh_from_db()

    with pytest.raises(AdmissaoInvalida, match='anonimizado'):
        admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                          data_inicio=HOJE)


@pytest.mark.django_db
def test_exige_cargo_e_data(cenario):
    with pytest.raises(AdmissaoInvalida, match='cargo'):
        admitir_candidato(cenario['candidato'], cargo=None, data_inicio=HOJE)

    with pytest.raises(AdmissaoInvalida, match='data de início'):
        admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                          data_inicio=None)


@pytest.mark.django_db
def test_cargo_de_outro_tenant_e_recusado(cenario):
    outro = TenantFactory(modulo_people=True)
    cargo_alheio = Cargo.all_tenants.create(tenant=outro, nome='Alheio')

    with pytest.raises(AdmissaoInvalida, match='outro tenant'):
        admitir_candidato(cenario['candidato'], cargo=cargo_alheio,
                          data_inicio=HOJE)


@pytest.mark.django_db
def test_conflito_de_dedup_nao_cria_segunda_linha(cenario):
    """
    Ex-funcionario voltando ja existe no DP. A R1 do modulo proibe a duplicata,
    e quem decide se e a mesma pessoa e o RH, nao o sistema.
    """
    from apps.people.services import registrar_colaborador

    # Mesma pessoa ja cadastrada no DP, com o mesmo telefone.
    registrar_colaborador(
        cenario['tenant'], cenario['unidade'],
        {'nome_completo': 'James Dean Vieira', 'telefone': '5589994395653'},
        origem='painel')
    antes = Colaborador.all_tenants.filter(tenant=cenario['tenant']).count()

    resultado = admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                                  data_inicio=HOJE)

    depois = Colaborador.all_tenants.filter(tenant=cenario['tenant']).count()
    assert resultado.acao == 'conflito'
    assert depois == antes
    cenario['candidato'].refresh_from_db()
    assert cenario['candidato'].colaborador_id is None   # nada foi ligado


# ── Pela tela ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_admite_pela_ficha(cenario):
    _cliente(cenario).post(
        reverse('people:candidato_admitir', args=[cenario['candidato'].pk]),
        {'cargo': cenario['cargo'].pk, 'data_inicio': HOJE.isoformat()})

    cenario['candidato'].refresh_from_db()
    assert cenario['candidato'].colaborador_id is not None


@pytest.mark.django_db
def test_ficha_esconde_o_botao_depois_de_admitir(cenario):
    """Botao "admitir" que nao admite mais e pior que botao nenhum."""
    cliente = _cliente(cenario)
    url = reverse('people:candidato_detalhe', args=[cenario['candidato'].pk])

    assert 'Enviar para o Departamento Pessoal' in cliente.get(url).content.decode()

    admitir_candidato(cenario['candidato'], cargo=cenario['cargo'],
                      data_inicio=HOJE)

    corpo = cliente.get(url).content.decode()
    assert 'ver ficha de colaborador' in corpo


@pytest.mark.django_db
def test_quem_so_ve_nao_admite(cenario):
    cliente = _cliente(cenario, funcionalidades=('people.ver',))

    resposta = cliente.post(
        reverse('people:candidato_admitir', args=[cenario['candidato'].pk]),
        {'cargo': cenario['cargo'].pk, 'data_inicio': HOJE.isoformat()})

    assert resposta.status_code == 403
