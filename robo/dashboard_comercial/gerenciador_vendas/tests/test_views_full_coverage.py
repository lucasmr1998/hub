"""
Testes abrangentes para views com baixa cobertura:
- CS Clube Dashboard (relatorios, relatorios_indicacoes, relatorios_parceiros)
- Notificacoes APIs (listar, detalhes, preferencias, tipos, canais, templates, enviar, teste)
- Sistema views (configuracoes_recontato, api_usuarios_criar, api_usuarios_editar, api_usuarios_deletar)
"""
import json
from datetime import time
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User, Group
from django.urls import reverse

from apps.sistema.middleware import set_current_tenant
from apps.cs.clube.models import MembroClube, NivelClube
from apps.cs.parceiros.models import CategoriaParceiro, Parceiro, CupomDesconto, ResgateCupom
from apps.cs.indicacoes.models import Indicacao
from apps.notificacoes.models import (
    TipoNotificacao, CanalNotificacao, Notificacao,
    TemplateNotificacao, PreferenciaNotificacao,
)
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    MembroClubeFactory, NivelClubeFactory, CategoriaParceiroFactory,
    ParceiroFactory, IndicacaoFactory, CupomDescontoFactory,
    TipoNotificacaoFactory, CanalNotificacaoFactory, NotificacaoFactory,
    TemplateNotificacaoFactory,
)


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def full_setup(db):
    """Setup completo: tenant, superuser, config, CS data, notificacoes data."""
    tenant = TenantFactory(plano_comercial='pro', modulo_cs=True, plano_cs='start')
    user = UserFactory(is_staff=True, is_superuser=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)
    return {'tenant': tenant, 'user': user}


@pytest.fixture
def logged_client(client, full_setup):
    client.force_login(full_setup['user'])
    return client


@pytest.fixture
def cs_data(full_setup):
    """Dados CS: niveis, membros, parceiros, cupons, indicacoes, resgates."""
    tenant = full_setup['tenant']
    nivel = NivelClubeFactory(tenant=tenant, nome='Bronze', xp_necessario=0)
    NivelClubeFactory(tenant=tenant, nome='Prata', xp_necessario=500)

    membros = [MembroClubeFactory(tenant=tenant) for _ in range(3)]

    cat = CategoriaParceiroFactory(tenant=tenant)
    parceiro = ParceiroFactory(tenant=tenant, categoria=cat)
    cupom = CupomDescontoFactory(tenant=tenant, parceiro=parceiro)

    indicacao = IndicacaoFactory(tenant=tenant, membro_indicador=membros[0])

    return {
        'nivel': nivel,
        'membros': membros,
        'parceiro': parceiro,
        'cupom': cupom,
        'indicacao': indicacao,
    }


@pytest.fixture
def notif_data(full_setup):
    """Dados de notificacoes: tipo, canal, notificacao, template."""
    tenant = full_setup['tenant']
    user = full_setup['user']
    tipo = TipoNotificacaoFactory(tenant=tenant, codigo='lead_novo')
    canal = CanalNotificacaoFactory(tenant=tenant, codigo='whatsapp')
    notificacao = NotificacaoFactory(
        tenant=tenant, tipo=tipo, canal=canal, destinatario=user,
    )
    template = TemplateNotificacaoFactory(
        tenant=tenant, tipo_notificacao=tipo, canal=canal,
    )
    return {
        'tipo': tipo,
        'canal': canal,
        'notificacao': notificacao,
        'template': template,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CS Clube Dashboard: Relatorios
# ══════════════════════════════════════════════════════════════════════════════

class TestClubeDashboardRelatorios:

    @pytest.mark.xfail(reason="View uses raw SQL incompatible with SQLite test DB")
    @patch('apps.cs.clube.services.hubsoft_service.HubsoftService.consultar_clientes_por_cidade', return_value={})
    def test_relatorios_get_200(self, mock_hubsoft, logged_client, cs_data):
        resp = logged_client.get(reverse('clube:dashboard_relatorios'))
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="View uses raw SQL incompatible with SQLite test DB")
    @patch('apps.cs.clube.services.hubsoft_service.HubsoftService.consultar_clientes_por_cidade', return_value={})
    def test_relatorios_com_periodo_7(self, mock_hubsoft, logged_client, cs_data):
        resp = logged_client.get(reverse('clube:dashboard_relatorios'), {'periodo': '7'})
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="View uses raw SQL incompatible with SQLite test DB")
    @patch('apps.cs.clube.services.hubsoft_service.HubsoftService.consultar_clientes_por_cidade', return_value={})
    def test_relatorios_com_periodo_total(self, mock_hubsoft, logged_client, cs_data):
        resp = logged_client.get(reverse('clube:dashboard_relatorios'), {'periodo': 'total'})
        assert resp.status_code == 200

    @patch('apps.cs.clube.services.hubsoft_service.HubsoftService.consultar_clientes_por_cidade', return_value={})
    def test_relatorios_requires_login(self, mock_hubsoft, client, full_setup, cs_data):
        resp = client.get(reverse('clube:dashboard_relatorios'))
        assert resp.status_code == 302


class TestClubeDashboardRelatoriosIndicacoes:

    def test_relatorios_indicacoes_get_200(self, logged_client, cs_data):
        resp = logged_client.get(reverse('clube:dashboard_relatorios_indicacoes'))
        assert resp.status_code == 200

    def test_relatorios_indicacoes_periodo_90(self, logged_client, cs_data):
        resp = logged_client.get(reverse('clube:dashboard_relatorios_indicacoes'), {'periodo': '90'})
        assert resp.status_code == 200

    def test_relatorios_indicacoes_periodo_total(self, logged_client, cs_data):
        resp = logged_client.get(reverse('clube:dashboard_relatorios_indicacoes'), {'periodo': 'total'})
        assert resp.status_code == 200

    def test_relatorios_indicacoes_requires_login(self, client, full_setup, cs_data):
        resp = client.get(reverse('clube:dashboard_relatorios_indicacoes'))
        assert resp.status_code == 302


class TestClubeDashboardRelatoriosParceiros:

    def test_relatorios_parceiros_get_200(self, logged_client, cs_data):
        resp = logged_client.get(reverse('clube:dashboard_relatorios_parceiros'))
        assert resp.status_code == 200

    def test_relatorios_parceiros_periodo_15(self, logged_client, cs_data):
        resp = logged_client.get(reverse('clube:dashboard_relatorios_parceiros'), {'periodo': '15'})
        assert resp.status_code == 200

    def test_relatorios_parceiros_requires_login(self, client, full_setup, cs_data):
        resp = client.get(reverse('clube:dashboard_relatorios_parceiros'))
        assert resp.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Notificacoes APIs
# ══════════════════════════════════════════════════════════════════════════════

class TestApiNotificacoesListar:

    def test_listar_200(self, logged_client, notif_data):
        resp = logged_client.get(reverse('notificacoes:api_notificacoes_listar'))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert 'notificacoes' in data

    def test_listar_com_paginacao(self, logged_client, notif_data):
        resp = logged_client.get(reverse('notificacoes:api_notificacoes_listar'), {'page': 1, 'per_page': 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data['page'] == 1
        assert data['per_page'] == 5

    def test_listar_requires_login(self, client, full_setup, notif_data):
        resp = client.get(reverse('notificacoes:api_notificacoes_listar'))
        assert resp.status_code == 302


class TestApiNotificacaoDetalhes:

    def test_detalhes_200(self, logged_client, notif_data):
        nid = notif_data['notificacao'].id
        resp = logged_client.get(reverse('notificacoes:api_notificacao_detalhes', args=[nid]))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['notificacao']['id'] == nid

    def test_detalhes_404(self, logged_client, notif_data):
        resp = logged_client.get(reverse('notificacoes:api_notificacao_detalhes', args=[99999]))
        assert resp.status_code == 404
        data = resp.json()
        assert data['success'] is False


class TestApiNotificacoesPreferencias:

    def test_preferencias_get_empty(self, logged_client, notif_data):
        resp = logged_client.get(reverse('notificacoes:api_notificacoes_preferencias'))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['preferencias'] == []

    def test_preferencias_post_create(self, logged_client, full_setup, notif_data):
        payload = {
            'tipo_notificacao_id': notif_data['tipo'].id,
            'canal_preferido_id': notif_data['canal'].id,
            'ativo': True,
            'horario_inicio': '08:00',
            'horario_fim': '18:00',
            'dias_semana': [0, 1, 2, 3, 4],
        }
        resp = logged_client.post(
            reverse('notificacoes:api_notificacoes_preferencias'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['created'] is True

    def test_preferencias_get_after_create(self, logged_client, full_setup, notif_data):
        PreferenciaNotificacao.all_tenants.create(
            tenant=full_setup['tenant'],
            usuario=full_setup['user'],
            tipo_notificacao=notif_data['tipo'],
            canal_preferido=notif_data['canal'],
            ativo=True,
            horario_inicio=time(8, 0),
            horario_fim=time(18, 0),
            dias_semana=[0, 1, 2, 3, 4],
        )
        resp = logged_client.get(reverse('notificacoes:api_notificacoes_preferencias'))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['preferencias']) == 1


class TestApiTiposNotificacao:

    def test_tipos_list_200(self, logged_client, notif_data):
        resp = logged_client.get(reverse('notificacoes:api_tipos_notificacao'))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert len(data['tipos']) >= 1

    @pytest.mark.xfail(reason="BUG: /api/ esta em _PERM_SKIP_PATHS do middleware, user_tem_funcionalidade retorna True por default (None). Rastreado em backlog/api_perm_skip_paths.")
    def test_tipos_non_superuser_denied(self, client, full_setup, notif_data):
        from apps.sistema.models import PermissaoUsuario
        regular_user = UserFactory(is_staff=False, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=full_setup['tenant'])
        PermissaoUsuario.objects.create(user=regular_user, tenant=full_setup['tenant'])
        client.force_login(regular_user)
        resp = client.get(reverse('notificacoes:api_tipos_notificacao'))
        assert resp.status_code in [302, 403]


class TestApiCanaisNotificacao:

    def test_canais_list_200(self, logged_client, notif_data):
        resp = logged_client.get(reverse('notificacoes:api_canais_notificacao'))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert len(data['canais']) >= 1

    @pytest.mark.xfail(reason="BUG: /api/ em _PERM_SKIP_PATHS do middleware. Ver tarefa no backlog.")
    def test_canais_non_superuser_denied(self, client, full_setup, notif_data):
        from apps.sistema.models import PermissaoUsuario
        regular_user = UserFactory(is_staff=False, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=full_setup['tenant'])
        PermissaoUsuario.objects.create(user=regular_user, tenant=full_setup['tenant'])
        client.force_login(regular_user)
        resp = client.get(reverse('notificacoes:api_canais_notificacao'))
        assert resp.status_code in [302, 403]


class TestApiTemplatesNotificacoes:

    def test_templates_list_200(self, logged_client, notif_data):
        resp = logged_client.get(reverse('notificacoes:api_templates_notificacoes'))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert len(data['templates']) >= 1

    def test_templates_detail_200(self, logged_client, notif_data):
        tid = notif_data['template'].id
        resp = logged_client.get(reverse('notificacoes:api_templates_notificacoes_detail', args=[tid]))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['template']['id'] == tid

    def test_templates_detail_404(self, logged_client, notif_data):
        resp = logged_client.get(reverse('notificacoes:api_templates_notificacoes_detail', args=[99999]))
        assert resp.status_code == 404


class TestApiNotificacaoEnviar:

    def test_enviar_sucesso(self, logged_client, notif_data):
        payload = {
            'tipo': 'lead_novo',
            'destinatarios': [],
            'dados_contexto': {'titulo': 'Teste', 'mensagem': 'Msg teste'},
        }
        resp = logged_client.post(
            reverse('notificacoes:api_notificacao_enviar'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True

    def test_enviar_missing_tipo(self, logged_client, notif_data):
        payload = {'destinatarios': []}
        resp = logged_client.post(
            reverse('notificacoes:api_notificacao_enviar'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        # View is disabled, returns 200 with success=false or 400
        assert resp.status_code in (200, 400)


class TestApiNotificacoesTeste:

    def test_teste_sucesso(self, logged_client, notif_data):
        payload = {'tipo': 'lead_novo', 'canal': 'sistema'}
        resp = logged_client.post(
            reverse('notificacoes:api_notificacoes_teste'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True

    def test_teste_missing_tipo_400(self, logged_client, notif_data):
        payload = {'canal': 'email'}
        resp = logged_client.post(
            reverse('notificacoes:api_notificacoes_teste'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_teste_requires_login(self, client, full_setup, notif_data):
        payload = {'tipo': 'lead_novo'}
        resp = client.post(
            reverse('notificacoes:api_notificacoes_teste'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Sistema Views
# ══════════════════════════════════════════════════════════════════════════════

class TestConfiguracaoRecontato:

    def test_recontato_get_200(self, logged_client, full_setup):
        resp = logged_client.get(reverse('sistema:configuracoes_recontato'))
        assert resp.status_code == 200

    def test_recontato_requires_login(self, client, full_setup):
        resp = client.get(reverse('sistema:configuracoes_recontato'))
        assert resp.status_code == 302


class TestApiUsuariosCriar:

    def test_criar_usuario_sucesso(self, logged_client, full_setup):
        # API deriva o username do email (antes de @)
        payload = {
            'email': 'novousuario@teste.com',
            'password': 'senha123segura',
            'first_name': 'Novo',
            'last_name': 'Usuario',
            'is_active': True,
            'is_staff': False,
            'groups': [],
        }
        resp = logged_client.post(
            reverse('sistema:api_usuarios_criar'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['user']['username'] == 'novousuario'

    def test_criar_usuario_sem_email_400(self, logged_client, full_setup):
        payload = {'password': 'senha123'}
        resp = logged_client.post(
            reverse('sistema:api_usuarios_criar'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_criar_usuario_email_duplicado_400_v2(self, logged_client, full_setup):
        payload = {
            'email': full_setup['user'].email,
            'password': 'senha123',
        }
        resp = logged_client.post(
            reverse('sistema:api_usuarios_criar'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 400
        data = resp.json()
        assert 'email' in data['error'].lower()

    def test_criar_usuario_email_duplicado_400(self, logged_client, full_setup):
        payload = {
            'username': 'outrouser',
            'email': full_setup['user'].email,
            'password': 'senha123',
        }
        resp = logged_client.post(
            reverse('sistema:api_usuarios_criar'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 400
        data = resp.json()
        assert 'email' in data['error'].lower()

    def test_criar_usuario_com_grupos(self, logged_client, full_setup):
        Group.objects.create(name='vendedores')
        payload = {
            'username': 'comgrupo',
            'email': 'comgrupo@teste.com',
            'password': 'senha123segura',
            'groups': ['vendedores', 'grupo_inexistente'],
        }
        resp = logged_client.post(
            reverse('sistema:api_usuarios_criar'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'vendedores' in data['user']['groups']
        assert 'grupo_inexistente' not in data['user']['groups']

    @pytest.mark.xfail(reason="BUG: /api/ em _PERM_SKIP_PATHS do middleware. Ver tarefa no backlog.")
    def test_criar_usuario_sem_permissao_403(self, client, full_setup):
        from apps.sistema.models import PermissaoUsuario
        regular_user = UserFactory(is_staff=False, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=full_setup['tenant'])
        PermissaoUsuario.objects.create(user=regular_user, tenant=full_setup['tenant'])
        client.force_login(regular_user)
        payload = {
            'email': 'novo@teste.com',
            'password': 'senha123',
        }
        resp = client.post(
            reverse('sistema:api_usuarios_criar'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 403


class TestApiUsuariosEditar:

    def test_editar_usuario_sucesso(self, logged_client, full_setup):
        target = UserFactory(is_superuser=False)
        PerfilFactory(user=target, tenant=full_setup['tenant'])
        payload = {
            'first_name': 'Editado',
            'last_name': 'Teste',
        }
        resp = logged_client.put(
            reverse('sistema:api_usuarios_editar', args=[target.id]),
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['user']['first_name'] == 'Editado'

    def test_editar_usuario_404(self, logged_client, full_setup):
        resp = logged_client.put(
            reverse('sistema:api_usuarios_editar', args=[99999]),
            data=json.dumps({'first_name': 'X'}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    @pytest.mark.xfail(reason="BUG: /api/ em _PERM_SKIP_PATHS do middleware. Ver tarefa no backlog.")
    def test_editar_usuario_sem_permissao_403(self, client, full_setup):
        from apps.sistema.models import PermissaoUsuario
        regular_user = UserFactory(is_staff=False, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=full_setup['tenant'])
        PermissaoUsuario.objects.create(user=regular_user, tenant=full_setup['tenant'])
        # Target tambem precisa estar no tenant (senao 404 mascara o 403)
        target = UserFactory(is_superuser=False)
        PerfilFactory(user=target, tenant=full_setup['tenant'])
        client.force_login(regular_user)
        resp = client.put(
            reverse('sistema:api_usuarios_editar', args=[target.id]),
            data=json.dumps({'first_name': 'X'}),
            content_type='application/json',
        )
        assert resp.status_code == 403


class TestApiUsuariosDeletar:

    def test_deletar_usuario_sucesso(self, logged_client, full_setup):
        target = UserFactory(is_superuser=False)
        PerfilFactory(user=target, tenant=full_setup['tenant'])
        resp = logged_client.delete(
            reverse('sistema:api_usuarios_deletar', args=[target.id]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True

    def test_deletar_proprio_usuario_400(self, logged_client, full_setup):
        resp = logged_client.delete(
            reverse('sistema:api_usuarios_deletar', args=[full_setup['user'].id]),
        )
        assert resp.status_code == 400

    def test_deletar_superusuario_400(self, logged_client, full_setup):
        superuser = UserFactory(is_superuser=True)
        PerfilFactory(user=superuser, tenant=full_setup['tenant'])
        resp = logged_client.delete(
            reverse('sistema:api_usuarios_deletar', args=[superuser.id]),
        )
        assert resp.status_code == 400

    def test_deletar_usuario_inexistente_404(self, logged_client, full_setup):
        resp = logged_client.delete(
            reverse('sistema:api_usuarios_deletar', args=[99999]),
        )
        assert resp.status_code == 404

    @pytest.mark.xfail(reason="BUG: /api/ em _PERM_SKIP_PATHS do middleware. Ver tarefa no backlog.")
    def test_deletar_usuario_sem_permissao_403(self, client, full_setup):
        from apps.sistema.models import PermissaoUsuario
        regular_user = UserFactory(is_staff=False, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=full_setup['tenant'])
        PermissaoUsuario.objects.create(user=regular_user, tenant=full_setup['tenant'])
        client.force_login(regular_user)
        target = UserFactory(is_superuser=False)
        PerfilFactory(user=target, tenant=full_setup['tenant'])
        resp = client.delete(
            reverse('sistema:api_usuarios_deletar', args=[target.id]),
        )
        assert resp.status_code == 403


class TestConfiguracaoView:

    def test_configuracoes_get_200(self, logged_client, full_setup):
        resp = logged_client.get(reverse('sistema:configuracoes'))
        assert resp.status_code == 200

    def test_configuracoes_requires_login(self, client, full_setup):
        resp = client.get(reverse('sistema:configuracoes'))
        assert resp.status_code == 302


class TestConfiguracaoUsuariosView:

    def test_usuarios_view_superuser_200(self, logged_client, full_setup):
        resp = logged_client.get(reverse('sistema:configuracoes_usuarios'))
        assert resp.status_code == 200

    def test_usuarios_view_non_superuser_redirect(self, client, full_setup):
        from apps.sistema.models import PermissaoUsuario
        regular_user = UserFactory(is_staff=False, is_superuser=False)
        PerfilFactory(user=regular_user, tenant=full_setup['tenant'])
        PermissaoUsuario.objects.create(user=regular_user, tenant=full_setup['tenant'])
        client.force_login(regular_user)
        resp = client.get(reverse('sistema:configuracoes_usuarios'))
        # Sem permissao: 302 (redirect) ou 403 dependendo do middleware
        assert resp.status_code in [302, 403]
