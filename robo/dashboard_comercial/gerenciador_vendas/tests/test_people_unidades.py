"""
Testes do CRUD de unidade.

Dois assuntos concentram os casos: o booleano de tres estados (herdar, sim, nao),
que um checkbox comum nao consegue representar, e o fato de unidade nao se
apagar. Os dois falham de um jeito que so aparece semanas depois.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.people.models import Colaborador, Unidade
from apps.people.services import config_efetiva, registrar_colaborador
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


CODIGOS_PERMISSAO = ['people.ver', 'people.gerir_unidades']


@pytest.fixture
def tenant(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant, nome_empresa=tenant.nome, ativo=True)
    return tenant


def _usuario(tenant, username='gestora', funcionalidades=CODIGOS_PERMISSAO):
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


def _dados(**extra):
    base = {
        'nome': 'Unidade Centro',
        'codigo': 'unidade-centro',
        'cnpj': '', 'telefone': '', 'cep': '', 'rua': '', 'numero': '',
        'complemento': '', 'bairro': '', 'cidade': '', 'estado': '',
        'responsavel': '', 'ativo': 'on',
        'dias_experiencia_padrao': '', 'dias_primeiro_periodo_experiencia': '',
        'exige_cpf_no_autocadastro': '',
    }
    base.update(extra)
    return base


# ──────────────────────────────────────────────
# Criar e editar
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_cria_unidade(tenant):
    cliente = _usuario(tenant)
    resposta = cliente.post('/people/unidades/nova/', _dados(), follow=True)

    assert resposta.status_code == 200
    unidade = Unidade.all_tenants.get(tenant=tenant, codigo='unidade-centro')
    assert unidade.nome == 'Unidade Centro'
    assert unidade.ativo is True


@pytest.mark.django_db
def test_unidade_nasce_no_tenant_de_quem_criou(tenant):
    """A view seta o tenant explicitamente. Sem isso a unidade nasce orfa."""
    cliente = _usuario(tenant)
    cliente.post('/people/unidades/nova/', _dados())

    unidade = Unidade.all_tenants.get(codigo='unidade-centro')
    assert unidade.tenant_id == tenant.pk


@pytest.mark.django_db
def test_codigo_duplicado_vira_erro_de_campo_e_nao_500(tenant):
    """
    A unique do banco ja barraria, mas com IntegrityError na cara do usuario.
    O form transforma isso em mensagem no campo certo.
    """
    cliente = _usuario(tenant)
    cliente.post('/people/unidades/nova/', _dados())
    resposta = cliente.post('/people/unidades/nova/', _dados(nome='Outra'))

    assert resposta.status_code == 200
    assert Unidade.all_tenants.filter(tenant=tenant).count() == 1
    assert b'Ja existe uma unidade com este codigo' in resposta.content


@pytest.mark.django_db
def test_mesmo_codigo_em_outro_tenant_e_permitido(tenant):
    """Unicidade e por tenant."""
    outro = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=outro, nome_empresa=outro.nome, ativo=True)
    Unidade.all_tenants.create(tenant=outro, nome='Centro', codigo='unidade-centro')

    _usuario(tenant).post('/people/unidades/nova/', _dados())
    assert Unidade.all_tenants.filter(codigo='unidade-centro').count() == 2


@pytest.mark.django_db
def test_edita_unidade(tenant):
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Antigo', codigo='loja')
    cliente = _usuario(tenant)

    cliente.post(f'/people/unidades/{unidade.pk}/',
                 _dados(nome='Nome Novo', codigo='loja'))

    unidade.refresh_from_db()
    assert unidade.nome == 'Nome Novo'


@pytest.mark.django_db
def test_editar_mantendo_o_proprio_codigo_nao_acusa_duplicata(tenant):
    """O clean precisa excluir a propria instancia da checagem."""
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja', codigo='loja')
    cliente = _usuario(tenant)

    resposta = cliente.post(f'/people/unidades/{unidade.pk}/',
                            _dados(nome='Loja Editada', codigo='loja'), follow=True)

    assert b'Ja existe uma unidade' not in resposta.content
    unidade.refresh_from_db()
    assert unidade.nome == 'Loja Editada'


@pytest.mark.django_db
def test_normaliza_cep_telefone_e_uf(tenant):
    cliente = _usuario(tenant)
    cliente.post('/people/unidades/nova/', _dados(
        cep='64000000', telefone='(86) 3222-1111', estado='pi'))

    unidade = Unidade.all_tenants.get(codigo='unidade-centro')
    assert unidade.cep == '64000-000'
    assert unidade.telefone == '558632221111'
    assert unidade.estado == 'PI'


# ──────────────────────────────────────────────
# O booleano de tres estados
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_override_vazio_significa_herdar(tenant):
    """
    Um BooleanField comum colapsaria None em False, e a unidade passaria a
    dizer "nao exigir CPF" quando queria dizer "usar o que o tenant definiu".
    """
    cliente = _usuario(tenant)
    cliente.post('/people/unidades/nova/', _dados(exige_cpf_no_autocadastro=''))

    unidade = Unidade.all_tenants.get(codigo='unidade-centro')
    assert unidade.exige_cpf_no_autocadastro is None
    assert config_efetiva(unidade).exige_cpf_no_autocadastro is True  # default do tenant


@pytest.mark.django_db
def test_override_nao_desliga_de_verdade(tenant):
    cliente = _usuario(tenant)
    cliente.post('/people/unidades/nova/', _dados(exige_cpf_no_autocadastro='nao'))

    unidade = Unidade.all_tenants.get(codigo='unidade-centro')
    assert unidade.exige_cpf_no_autocadastro is False
    assert config_efetiva(unidade).exige_cpf_no_autocadastro is False


@pytest.mark.django_db
def test_override_sim_liga(tenant):
    cliente = _usuario(tenant)
    cliente.post('/people/unidades/nova/', _dados(exige_cpf_no_autocadastro='sim'))

    unidade = Unidade.all_tenants.get(codigo='unidade-centro')
    assert unidade.exige_cpf_no_autocadastro is True


@pytest.mark.django_db
def test_form_de_edicao_mostra_o_estado_atual_do_override(tenant):
    """Sem o initial, reeditar a unidade zeraria o override sem querer."""
    unidade = Unidade.all_tenants.create(
        tenant=tenant, nome='Loja', codigo='loja', exige_cpf_no_autocadastro=False)
    cliente = _usuario(tenant)

    resposta = cliente.get(f'/people/unidades/{unidade.pk}/')
    assert resposta.context['form'].initial['exige_cpf_no_autocadastro'] == 'nao'


@pytest.mark.django_db
def test_dias_de_experiencia_por_unidade_valem_no_calculo(tenant):
    cliente = _usuario(tenant)
    cliente.post('/people/unidades/nova/', _dados(dias_primeiro_periodo_experiencia='30'))

    unidade = Unidade.all_tenants.get(codigo='unidade-centro')
    assert config_efetiva(unidade).dias_primeiro_periodo_experiencia == 30


# ──────────────────────────────────────────────
# Unidade nao se apaga
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_desativa_em_vez_de_apagar(tenant):
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja', codigo='loja')
    cliente = _usuario(tenant)

    cliente.post(f'/people/unidades/{unidade.pk}/alternar-ativo/')

    unidade.refresh_from_db()
    assert unidade.ativo is False
    assert Unidade.all_tenants.filter(pk=unidade.pk).exists()


@pytest.mark.django_db
def test_reativa(tenant):
    unidade = Unidade.all_tenants.create(
        tenant=tenant, nome='Loja', codigo='loja', ativo=False)
    cliente = _usuario(tenant)

    cliente.post(f'/people/unidades/{unidade.pk}/alternar-ativo/')

    unidade.refresh_from_db()
    assert unidade.ativo is True


@pytest.mark.django_db
def test_desativar_preserva_os_colaboradores(tenant):
    """
    E o ponto do soft delete: a loja sai de circulacao, a equipe continua
    rastreavel. Apagar seria impossivel de qualquer forma, o PROTECT barra.
    """
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja', codigo='loja')
    registrar_colaborador(tenant, unidade, {'nome_completo': 'Maria'}, origem='rh')
    cliente = _usuario(tenant)

    cliente.post(f'/people/unidades/{unidade.pk}/alternar-ativo/')

    assert Colaborador.all_tenants.filter(unidade=unidade).count() == 1


@pytest.mark.django_db
def test_alternar_ativo_so_aceita_post(tenant):
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja', codigo='loja')
    cliente = _usuario(tenant)

    assert cliente.get(f'/people/unidades/{unidade.pk}/alternar-ativo/').status_code == 405


# ──────────────────────────────────────────────
# Permissao e isolamento
# ──────────────────────────────────────────────

@pytest.mark.django_db
def test_quem_so_ve_nao_cria(tenant):
    cliente = _usuario(tenant, 'leitora', funcionalidades=['people.ver'])
    assert cliente.get('/people/unidades/nova/').status_code == 403
    assert cliente.post('/people/unidades/nova/', _dados()).status_code == 403


@pytest.mark.django_db
def test_quem_so_ve_nao_desativa(tenant):
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja', codigo='loja')
    cliente = _usuario(tenant, 'leitora', funcionalidades=['people.ver'])

    assert cliente.post(f'/people/unidades/{unidade.pk}/alternar-ativo/').status_code == 403
    unidade.refresh_from_db()
    assert unidade.ativo is True


@pytest.mark.django_db
def test_lista_esconde_acoes_de_quem_so_ve(tenant):
    Unidade.all_tenants.create(tenant=tenant, nome='Loja', codigo='loja')
    cliente = _usuario(tenant, 'leitora', funcionalidades=['people.ver'])

    corpo = cliente.get('/people/unidades/').content.decode()
    assert 'Nova unidade' not in corpo
    assert 'alternar-ativo' not in corpo


@pytest.mark.django_db
def test_nao_edita_unidade_de_outro_tenant(tenant):
    outro = TenantFactory(modulo_people=True)
    alheia = Unidade.all_tenants.create(tenant=outro, nome='Alheia', codigo='alheia')
    cliente = _usuario(tenant)

    assert cliente.get(f'/people/unidades/{alheia.pk}/').status_code == 404


@pytest.mark.django_db
def test_lista_nao_mostra_unidade_de_outro_tenant(tenant):
    outro = TenantFactory(modulo_people=True)
    Unidade.all_tenants.create(tenant=outro, nome='Loja Alheia', codigo='alheia')
    Unidade.all_tenants.create(tenant=tenant, nome='Loja Minha', codigo='minha')
    cliente = _usuario(tenant)

    corpo = cliente.get('/people/unidades/').content.decode()
    assert 'Loja Minha' in corpo
    assert 'Loja Alheia' not in corpo


@pytest.mark.django_db
def test_contador_so_conta_colaborador_ativo(tenant):
    from apps.people import estados
    from apps.people.services import mover_situacao

    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja', codigo='loja')
    registrar_colaborador(tenant, unidade, {'nome_completo': 'Ativa'}, origem='rh')
    saiu = registrar_colaborador(tenant, unidade, {'nome_completo': 'Saiu'}, origem='rh')
    mover_situacao(saiu.colaborador, estados.SITUACAO_DESLIGADO, motivo='Nao compareceu')

    cliente = _usuario(tenant)
    unidades = cliente.get('/people/unidades/').context['unidades']
    assert unidades[0].total_colaboradores == 1
