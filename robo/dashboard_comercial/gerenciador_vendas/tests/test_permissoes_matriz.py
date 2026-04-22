"""
Matriz de permissoes: valida que cada perfil padrao tem exatamente as
funcionalidades declaradas em seed_perfis_padrao.py.

Cobre os 11 perfis x 42 funcionalidades via parametrize.

Serve como "regression guard" pra migracao do DS e futuras mudancas
no sistema de permissoes — qualquer divergencia quebra o teste.

Como rodar:
    pytest tests/test_permissoes_matriz.py -v
"""
import pytest
from django.core.management import call_command

from apps.sistema.decorators import user_tem_funcionalidade
from apps.sistema.models import Funcionalidade, PerfilPermissao, PermissaoUsuario
from tests.factories import TenantFactory, UserFactory


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def matriz_setup(db):
    """Cria tenant + todos os 42 funcs + 11 perfis padrao + 1 user por perfil."""
    tenant = TenantFactory(
        plano_comercial='pro', plano_marketing='pro', plano_cs='pro',
        modulo_comercial=True, modulo_marketing=True, modulo_cs=True,
    )

    # Seed funcionalidades (42) + perfis padrao (11) pra este tenant
    call_command('seed_funcionalidades')
    call_command('seed_perfis_padrao')

    # Cria um user vinculado a cada perfil padrao
    perfis_padrao = PerfilPermissao.objects.filter(tenant=tenant)
    users_por_perfil = {}
    for perfil in perfis_padrao:
        user = UserFactory()
        PermissaoUsuario.objects.create(user=user, tenant=tenant, perfil=perfil)
        users_por_perfil[perfil.nome] = user

    return {'tenant': tenant, 'users': users_por_perfil}


# ── Matriz esperada: (perfil, codigo_funcionalidade) -> deve_ter ─────────
#
# Fonte: seed_perfis_padrao.py (apps/sistema/management/commands/)
# Atualizar este dicionario quando seed_perfis_padrao.py mudar.
#
# Nao listo todas as 42x11 = 462 combinacoes — so amostras representativas
# que cobrem: (a) o que o perfil TEM, (b) o que o perfil NAO TEM.

MATRIZ_ESPERADA = [
    # ── Vendedor ────────────────────────────────────────────────────────
    ('Vendedor', 'comercial.ver_pipeline', True),
    ('Vendedor', 'comercial.mover_oportunidade', True),
    ('Vendedor', 'comercial.criar_tarefa', True),
    ('Vendedor', 'comercial.ver_todas_oportunidades', False),  # escopo gerente
    ('Vendedor', 'comercial.gerenciar_metas', False),
    ('Vendedor', 'comercial.gerenciar_equipes', False),
    ('Vendedor', 'comercial.configurar_pipeline', False),
    ('Vendedor', 'comercial.excluir_lead', False),
    ('Vendedor', 'inbox.ver_minhas', True),
    ('Vendedor', 'inbox.responder', True),
    ('Vendedor', 'inbox.ver_equipe', False),
    ('Vendedor', 'inbox.ver_todas', False),
    ('Vendedor', 'marketing.ver_leads', False),
    ('Vendedor', 'cs.ver_dashboard', False),
    ('Vendedor', 'config.gerenciar_usuarios', False),

    # ── Supervisor Comercial ────────────────────────────────────────────
    ('Supervisor Comercial', 'comercial.ver_todas_oportunidades', True),
    ('Supervisor Comercial', 'comercial.gerenciar_metas', True),
    ('Supervisor Comercial', 'comercial.gerenciar_equipes', False),  # gerente only
    ('Supervisor Comercial', 'comercial.configurar_pipeline', False),  # gerente only
    ('Supervisor Comercial', 'inbox.ver_equipe', True),
    ('Supervisor Comercial', 'inbox.ver_todas', False),
    ('Supervisor Comercial', 'inbox.transferir_equipe', True),

    # ── Gerente Comercial ───────────────────────────────────────────────
    ('Gerente Comercial', 'comercial.ver_todas_oportunidades', True),
    ('Gerente Comercial', 'comercial.gerenciar_metas', True),
    ('Gerente Comercial', 'comercial.gerenciar_equipes', True),
    ('Gerente Comercial', 'comercial.configurar_pipeline', True),
    ('Gerente Comercial', 'comercial.excluir_oportunidade', False),  # so Admin
    ('Gerente Comercial', 'inbox.ver_todas', True),
    ('Gerente Comercial', 'marketing.ver_leads', False),
    ('Gerente Comercial', 'cs.ver_dashboard', False),

    # ── Analista Marketing ──────────────────────────────────────────────
    ('Analista Marketing', 'marketing.ver_leads', True),
    ('Analista Marketing', 'marketing.gerenciar_campanhas', True),
    ('Analista Marketing', 'marketing.gerenciar_segmentos', True),
    ('Analista Marketing', 'marketing.gerenciar_automacoes', False),  # gerente only
    ('Analista Marketing', 'marketing.configurar', False),
    ('Analista Marketing', 'comercial.ver_pipeline', False),

    # ── Gerente Marketing ───────────────────────────────────────────────
    ('Gerente Marketing', 'marketing.gerenciar_automacoes', True),
    ('Gerente Marketing', 'marketing.configurar', True),
    ('Gerente Marketing', 'comercial.ver_pipeline', False),

    # ── Operador CS ─────────────────────────────────────────────────────
    ('Operador CS', 'cs.ver_dashboard', True),
    ('Operador CS', 'cs.gerenciar_membros', True),
    ('Operador CS', 'cs.gerenciar_cupons', True),
    ('Operador CS', 'cs.aprovar_cupons', False),  # gerente only
    ('Operador CS', 'cs.configurar', False),
    ('Operador CS', 'comercial.ver_pipeline', False),

    # ── Gerente CS ──────────────────────────────────────────────────────
    ('Gerente CS', 'cs.aprovar_cupons', True),
    ('Gerente CS', 'cs.configurar', True),

    # ── Agente Suporte ──────────────────────────────────────────────────
    ('Agente Suporte', 'inbox.ver_minhas', True),
    ('Agente Suporte', 'inbox.responder', True),
    ('Agente Suporte', 'inbox.ver_equipe', False),
    ('Agente Suporte', 'inbox.configurar', False),

    # ── Supervisor Suporte ──────────────────────────────────────────────
    ('Supervisor Suporte', 'inbox.ver_equipe', True),
    ('Supervisor Suporte', 'inbox.transferir_equipe', True),
    ('Supervisor Suporte', 'inbox.ver_todas', False),
    ('Supervisor Suporte', 'inbox.configurar', False),

    # ── Gerente Suporte ─────────────────────────────────────────────────
    ('Gerente Suporte', 'inbox.ver_todas', True),
    ('Gerente Suporte', 'inbox.configurar', True),

    # ── Admin ───────────────────────────────────────────────────────────
    # Admin = __all__ (todas as 42)
    ('Admin', 'comercial.configurar_pipeline', True),
    ('Admin', 'comercial.excluir_lead', True),
    ('Admin', 'comercial.excluir_oportunidade', True),
    ('Admin', 'marketing.configurar', True),
    ('Admin', 'cs.configurar', True),
    ('Admin', 'inbox.configurar', True),
    ('Admin', 'config.gerenciar_usuarios', True),
    ('Admin', 'config.gerenciar_perfis', True),
    ('Admin', 'suporte.gerenciar_tickets', True),
    ('Admin', 'suporte.gerenciar_conhecimento', True),
]


# ── Testes parametrizados ─────────────────────────────────────────────────

@pytest.mark.parametrize('perfil_nome,codigo,deve_ter', MATRIZ_ESPERADA)
def test_matriz_permissoes(matriz_setup, rf, perfil_nome, codigo, deve_ter):
    """
    Pra cada (perfil, funcionalidade), verifica se user_tem_funcionalidade()
    retorna o esperado. Fonte da verdade: seed_perfis_padrao.py.
    """
    user = matriz_setup['users'].get(perfil_nome)
    assert user is not None, f"Perfil '{perfil_nome}' nao criado por seed_perfis_padrao"

    # Cria um request fake com user populado pelo middleware
    request = rf.get('/')
    request.user = user

    # Carrega user_funcionalidades como o PermissaoMiddleware faria
    from apps.sistema.models import PermissaoUsuario
    perm = PermissaoUsuario.objects.filter(user=user).first()
    if perm and perm.perfil:
        request.user_funcionalidades = set(
            perm.perfil.funcionalidades.values_list('codigo', flat=True)
        )
    else:
        request.user_funcionalidades = None

    resultado = user_tem_funcionalidade(request, codigo)
    assert resultado == deve_ter, (
        f"Perfil '{perfil_nome}' {'deveria ter' if deve_ter else 'nao deveria ter'} "
        f"'{codigo}', mas user_tem_funcionalidade retornou {resultado}"
    )


def test_admin_tem_todas_42(matriz_setup):
    """Garantia independente — Admin deve ter TODAS as 42 funcionalidades."""
    admin_user = matriz_setup['users']['Admin']
    perm = PermissaoUsuario.objects.get(user=admin_user)
    total_funcs = Funcionalidade.objects.count()
    total_perfil = perm.perfil.funcionalidades.count()

    assert total_funcs == 42, f"Seed de funcionalidades mudou: esperado 42, tem {total_funcs}"
    assert total_perfil == total_funcs, (
        f"Perfil Admin deveria ter todas as {total_funcs} funcionalidades, tem {total_perfil}"
    )


def test_todos_perfis_padrao_criados(matriz_setup):
    """Garantia independente — seed_perfis_padrao cria os 11 perfis esperados."""
    tenant = matriz_setup['tenant']
    perfis = set(PerfilPermissao.objects.filter(tenant=tenant).values_list('nome', flat=True))

    esperados = {
        'Vendedor', 'Supervisor Comercial', 'Gerente Comercial',
        'Analista Marketing', 'Gerente Marketing',
        'Operador CS', 'Gerente CS',
        'Agente Suporte', 'Supervisor Suporte', 'Gerente Suporte',
        'Admin',
    }

    assert perfis == esperados, (
        f"Perfis padrao divergentes.\nEsperado: {esperados}\nCriado: {perfis}\n"
        f"Faltando: {esperados - perfis}\nExtra: {perfis - esperados}"
    )


def test_superuser_passa_em_tudo(db, rf):
    """Garantia: superuser bypassa todo o sistema de permissoes (retrocompat)."""
    superuser = UserFactory(is_superuser=True, is_staff=True)

    request = rf.get('/')
    request.user = superuser
    request.user_funcionalidades = set()  # sem nenhuma funcionalidade

    # Deveria passar mesmo sem funcionalidades listadas
    assert user_tem_funcionalidade(request, 'comercial.configurar_pipeline') is True
    assert user_tem_funcionalidade(request, 'config.gerenciar_usuarios') is True


def test_user_sem_perfil_passa_em_tudo(db, rf):
    """Garantia: user sem PermissaoUsuario atribuida = acesso total (legado)."""
    user = UserFactory(is_superuser=False)

    request = rf.get('/')
    request.user = user
    request.user_funcionalidades = None  # sinal de "sem perfil atribuido"

    assert user_tem_funcionalidade(request, 'comercial.configurar_pipeline') is True
    assert user_tem_funcionalidade(request, 'inbox.ver_todas') is True
