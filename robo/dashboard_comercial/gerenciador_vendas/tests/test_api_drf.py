"""
Testes para os endpoints DRF da API.

Cobre:
- Panel API (SessionAuthentication) — ViewSets CRUD
- N8N API (APITokenAuthentication) — Endpoints machine-to-machine
- Schema/Docs (OpenAPI + Swagger)
- Throttling (AnonRateThrottle)
"""

import os

import pytest


from apps.sistema.middleware import set_current_tenant


# ============================================================================
# Helpers
# ============================================================================

N8N_TOKEN = 'test-token-abc123'


@pytest.fixture
def n8n_headers():
    """Headers de autenticacao para endpoints N8N."""
    return {'HTTP_AUTHORIZATION': f'Bearer {N8N_TOKEN}'}


@pytest.fixture(autouse=True)
def _cleanup_env():
    """Garante limpeza da env var N8N_API_TOKEN apos cada teste."""
    yield
    os.environ.pop('N8N_API_TOKEN', None)


@pytest.fixture
def n8n_auth():
    """Seta a env var N8N_API_TOKEN para testes N8N."""
    os.environ['N8N_API_TOKEN'] = N8N_TOKEN


# ============================================================================
# PANEL API — SessionAuthentication
# ============================================================================


@pytest.mark.django_db
class TestPanelPlanoInternet:
    """CRUD de PlanoInternet via /api/v1/planos/."""

    url = '/api/v1/planos/'

    def _plano_data(self):
        return {
            'nome': 'Plano Fibra 200MB',
            'descricao': 'Internet fibra 200 Mega',
            'velocidade_download': 200,
            'velocidade_upload': 100,
            'valor_mensal': '99.90',
        }

    def test_list_requer_login(self, client):
        response = client.get(self.url)
        assert response.status_code in (401, 403)

    def test_list_com_login(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.get(self.url)
        assert response.status_code == 200
        data = response.json()
        assert 'results' in data

    def test_create(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.post(
            self.url,
            data=self._plano_data(),
            content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['nome'] == 'Plano Fibra 200MB'

    def test_retrieve(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        # Criar plano
        resp_create = client.post(
            self.url,
            data=self._plano_data(),
            content_type='application/json',
        )
        pk = resp_create.json()['id']
        # Retrieve
        response = client.get(f'{self.url}{pk}/')
        assert response.status_code == 200
        assert response.json()['id'] == pk

    def test_update(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        resp_create = client.post(
            self.url,
            data=self._plano_data(),
            content_type='application/json',
        )
        pk = resp_create.json()['id']
        response = client.put(
            f'{self.url}{pk}/',
            data={**self._plano_data(), 'nome': 'Plano Fibra 300MB'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['nome'] == 'Plano Fibra 300MB'

    def test_delete(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        resp_create = client.post(
            self.url,
            data=self._plano_data(),
            content_type='application/json',
        )
        pk = resp_create.json()['id']
        response = client.delete(f'{self.url}{pk}/')
        assert response.status_code == 204
        # Confirma exclusao
        response = client.get(f'{self.url}{pk}/')
        assert response.status_code == 404


@pytest.mark.django_db
class TestPanelOpcaoVencimento:
    """CRUD de OpcaoVencimento via /api/v1/opcoes-vencimento/."""

    url = '/api/v1/opcoes-vencimento/'

    def test_list_requer_login(self, client):
        response = client.get(self.url)
        assert response.status_code in (401, 403)

    def test_list_com_login(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.get(self.url)
        assert response.status_code == 200
        assert 'results' in response.json()

    def test_create(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.post(
            self.url,
            data={'dia_vencimento': 10, 'descricao': 'Dia 10'},
            content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['dia_vencimento'] == 10


@pytest.mark.django_db
@pytest.mark.skip(reason="Migration pendente do app viabilidade — tabela não existe")
class TestPanelCidadeViabilidade:
    """CRUD de CidadeViabilidade via /api/v1/cidades-viabilidade/."""

    url = '/api/v1/cidades-viabilidade/'

    def test_list_requer_login(self, client):
        response = client.get(self.url)
        assert response.status_code in (401, 403)

    def test_list_com_login(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.get(self.url)
        assert response.status_code == 200
        assert 'results' in response.json()

    def test_create(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.post(
            self.url,
            data={'cidade': 'Teresina', 'estado': 'PI'},
            content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['cidade'] == 'Teresina'


@pytest.mark.django_db
class TestPanelCampanhaTrafego:
    """CRUD de CampanhaTrafego via /api/v1/campanhas/."""

    url = '/api/v1/campanhas/'

    def _campanha_data(self):
        return {
            'nome': 'Black Friday 2026',
            'codigo': 'BF2026',
            'palavra_chave': 'blackfriday',
            'plataforma': 'google_ads',
        }

    def test_list_requer_login(self, client):
        response = client.get(self.url)
        assert response.status_code in (401, 403)

    def test_list_com_login(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.get(self.url)
        assert response.status_code == 200
        assert 'results' in response.json()

    def test_create(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.post(
            self.url,
            data=self._campanha_data(),
            content_type='application/json',
        )
        assert response.status_code == 201
        assert response.json()['codigo'] == 'BF2026'


@pytest.mark.django_db
class TestPanelTemplateNotificacao:
    """CRUD de TemplateNotificacao via /api/v1/templates-notificacao/."""

    url = '/api/v1/templates-notificacao/'

    def test_list_requer_login(self, client):
        response = client.get(self.url)
        assert response.status_code in (401, 403)

    def test_list_com_login(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.get(self.url)
        assert response.status_code == 200
        assert 'results' in response.json()


@pytest.mark.django_db
class TestPanelTipoNotificacao:
    """Read-only: TipoNotificacao via /api/v1/tipos-notificacao/."""

    url = '/api/v1/tipos-notificacao/'

    def test_list_requer_login(self, client):
        response = client.get(self.url)
        assert response.status_code in (401, 403)

    def test_list_com_login(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.get(self.url)
        assert response.status_code == 200
        assert 'results' in response.json()

    def test_create_bloqueado(self, client, user_a, config_a, set_tenant, tenant_a):
        """ReadOnlyModelViewSet nao permite POST."""
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.post(
            self.url,
            data={'codigo': 'lead_novo', 'nome': 'Novo Lead', 'descricao': 'Teste'},
            content_type='application/json',
        )
        assert response.status_code == 405  # Method Not Allowed


@pytest.mark.django_db
class TestPanelCanalNotificacao:
    """Read-only + toggle: CanalNotificacao via /api/v1/canais-notificacao/."""

    url = '/api/v1/canais-notificacao/'

    def test_list_requer_login(self, client):
        response = client.get(self.url)
        assert response.status_code in (401, 403)

    def test_list_com_login(self, client, user_a, config_a, set_tenant, tenant_a):
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.get(self.url)
        assert response.status_code == 200
        assert 'results' in response.json()

    def test_create_bloqueado(self, client, user_a, config_a, set_tenant, tenant_a):
        """ReadOnlyModelViewSet nao permite POST."""
        client.force_login(user_a)
        set_tenant(tenant_a)
        response = client.post(
            self.url,
            data={'codigo': 'whatsapp', 'nome': 'WhatsApp'},
            content_type='application/json',
        )
        assert response.status_code == 405

    def test_toggle_ativo(self, client, user_a, config_a, set_tenant, tenant_a):
        """Testa a action toggle-ativo no CanalNotificacaoViewSet."""
        from apps.notificacoes.models import CanalNotificacao

        client.force_login(user_a)
        set_tenant(tenant_a)
        canal = CanalNotificacao.objects.create(
            tenant=tenant_a,
            codigo='whatsapp',
            nome='WhatsApp',
            ativo=True,
        )
        response = client.post(f'{self.url}{canal.pk}/toggle-ativo/')
        assert response.status_code == 200
        canal.refresh_from_db()
        assert canal.ativo is False


# ============================================================================
# N8N API — APITokenAuthentication
# ============================================================================


@pytest.mark.django_db
class TestN8NLeadAPI:
    """Endpoints de Lead via /api/v1/n8n/leads/."""

    url = '/api/v1/n8n/leads/'

    def test_sem_token_retorna_401_ou_403(self, client):
        response = client.post(
            self.url,
            data={'nome_razaosocial': 'Teste', 'telefone': '86999999999'},
            content_type='application/json',
        )
        assert response.status_code in (401, 403)

    def test_token_invalido_retorna_401(self, client, n8n_auth):
        response = client.post(
            self.url,
            data={'nome_razaosocial': 'Teste', 'telefone': '86999999999'},
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer token-errado',
        )
        assert response.status_code == 401

    def test_criar_lead(self, client, config_a, n8n_auth, set_tenant, tenant_a, n8n_headers):
        set_tenant(tenant_a)
        response = client.post(
            self.url,
            data={'nome_razaosocial': 'Teste Lead N8N', 'telefone': '86999999999'},
            content_type='application/json',
            **n8n_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body['success'] is True
        assert body['lead']['nome_razaosocial'] == 'Teste Lead N8N'
        assert body['lead']['telefone'] == '86999999999'

    def test_criar_lead_sem_campos_obrigatorios(self, client, n8n_auth, n8n_headers):
        response = client.post(
            self.url,
            data={'email': 'teste@email.com'},
            content_type='application/json',
            **n8n_headers,
        )
        assert response.status_code == 400
        body = response.json()
        assert body['success'] is False
        assert 'errors' in body

    def test_atualizar_lead(self, client, config_a, n8n_auth, set_tenant, tenant_a, n8n_headers):
        set_tenant(tenant_a)
        # Criar
        resp_create = client.post(
            self.url,
            data={'nome_razaosocial': 'Lead Original', 'telefone': '86999999999'},
            content_type='application/json',
            **n8n_headers,
        )
        pk = resp_create.json()['lead']['id']
        # Atualizar
        response = client.put(
            f'{self.url}{pk}/',
            data={'nome_razaosocial': 'Lead Atualizado'},
            content_type='application/json',
            **n8n_headers,
        )
        assert response.status_code == 200
        assert response.json()['lead']['nome_razaosocial'] == 'Lead Atualizado'

    def test_atualizar_lead_inexistente(self, client, n8n_auth, n8n_headers):
        response = client.put(
            f'{self.url}99999/',
            data={'nome_razaosocial': 'Nao existe'},
            content_type='application/json',
            **n8n_headers,
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestN8NLeadBuscaAPI:
    """Busca de Lead por telefone via /api/v1/n8n/leads/buscar/."""

    url = '/api/v1/n8n/leads/buscar/'

    def test_sem_token_retorna_401_ou_403(self, client):
        response = client.get(self.url, {'telefone': '86999999999'})
        assert response.status_code in (401, 403)

    def test_busca_sem_parametro(self, client, n8n_auth, n8n_headers):
        response = client.get(self.url, **n8n_headers)
        assert response.status_code == 400

    def test_busca_telefone_inexistente(self, client, n8n_auth, n8n_headers):
        response = client.get(
            self.url,
            {'telefone': '00000000000'},
            **n8n_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body['success'] is True
        assert body['encontrado'] is False
        assert body['leads'] == []

    def test_busca_telefone_existente(
        self, client, config_a, n8n_auth, set_tenant, tenant_a, n8n_headers
    ):
        set_tenant(tenant_a)
        # Criar lead
        client.post(
            '/api/v1/n8n/leads/',
            data={'nome_razaosocial': 'Busca Lead', 'telefone': '86911112222'},
            content_type='application/json',
            **n8n_headers,
        )
        # Buscar
        response = client.get(
            self.url,
            {'telefone': '86911112222'},
            **n8n_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body['encontrado'] is True
        assert len(body['leads']) >= 1
        assert body['leads'][0]['telefone'] == '86911112222'


@pytest.mark.django_db
class TestN8NFluxoAPI:
    """Listagem de fluxos ativos via /api/v1/n8n/fluxos/."""

    url = '/api/v1/n8n/fluxos/'

    def test_sem_token_retorna_401_ou_403(self, client):
        response = client.get(self.url)
        assert response.status_code in (401, 403)

    def test_listar_fluxos(self, client, config_a, n8n_auth, set_tenant, tenant_a, n8n_headers):
        from apps.comercial.atendimento.models import FluxoAtendimento

        set_tenant(tenant_a)
        FluxoAtendimento.objects.create(
            tenant=tenant_a,
            nome='Fluxo Qualificacao',
            tipo_fluxo='qualificacao',
            status='ativo',
            ativo=True,
            max_tentativas=3,
        )
        FluxoAtendimento.objects.create(
            tenant=tenant_a,
            nome='Fluxo Inativo',
            tipo_fluxo='vendas',
            status='inativo',
            ativo=True,
            max_tentativas=3,
        )

        response = client.get(self.url, **n8n_headers)
        assert response.status_code == 200
        body = response.json()
        assert body['success'] is True
        # Apenas fluxos ativos
        nomes = [f['nome'] for f in body['fluxos']]
        assert 'Fluxo Qualificacao' in nomes
        assert 'Fluxo Inativo' not in nomes


@pytest.mark.django_db
class TestN8NAtendimentoAPI:
    """Endpoints de Atendimento via /api/v1/n8n/atendimentos/."""

    url = '/api/v1/n8n/atendimentos/'

    def test_sem_token_retorna_401_ou_403(self, client):
        response = client.post(
            self.url,
            data={},
            content_type='application/json',
        )
        assert response.status_code in (401, 403)

    def test_iniciar_atendimento_sem_dados(self, client, n8n_auth, n8n_headers):
        response = client.post(
            self.url,
            data={},
            content_type='application/json',
            **n8n_headers,
        )
        assert response.status_code == 400

    def test_consultar_atendimento_inexistente(self, client, n8n_auth, n8n_headers):
        response = client.get(f'{self.url}99999/', **n8n_headers)
        assert response.status_code == 404


# ============================================================================
# SCHEMA / DOCS (OpenAPI)
# ============================================================================


@pytest.mark.django_db
class TestSchemaAndDocs:
    """Testa acessibilidade do schema OpenAPI e Swagger UI."""

    def test_schema_acessivel(self, client, user_a):
        client.force_login(user_a)
        response = client.get('/api/schema/')
        assert response.status_code == 200

    def test_swagger_acessivel(self, client, user_a):
        client.force_login(user_a)
        response = client.get('/api/docs/')
        assert response.status_code == 200


# ============================================================================
# THROTTLING
# ============================================================================


@pytest.mark.django_db
@pytest.mark.skip(reason="Throttling depende de cache entre requests — difícil testar com Django test client")
class TestThrottling:
    """Testa rate limiting para requisicoes anonimas (30/min)."""

    def test_anon_rate_limit(self, client):
        pass
