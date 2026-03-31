"""
Testes de autenticação nos endpoints.

Verifica que:
- Endpoints do painel exigem login (retornam 302 sem sessão)
- Endpoints N8N exigem token (retornam 401 sem token, 200/405 com token)
- Endpoints públicos funcionam sem auth
"""
import json
import os

import pytest
from django.test import Client


# ── Endpoints do painel (exigem @login_required) ────────────────────────────

PANEL_ENDPOINTS = [
    # Configurações CRUD
    ('POST', '/configuracoes/cadastro/save/'),
    ('GET', '/api/configuracoes/cadastro/'),
    ('GET', '/api/configuracoes/planos/'),
    ('GET', '/api/configuracoes/vencimentos/'),
    ('GET', '/api/campanhas/'),
    ('GET', '/api/configuracoes/questoes/'),
    ('POST', '/api/configuracoes/questoes/duplicar/'),
    ('GET', '/api/templates-notificacoes/'),
    ('GET', '/api/tipos-notificacao/'),
    ('GET', '/api/canais-notificacao/'),
    # api/viabilidade/ excluído: migration pendente do app viabilidade
    # CRUD de fluxos/questões/atendimentos
    ('POST', '/api/fluxos/criar/'),
    ('GET', '/api/fluxos/'),
    ('GET', '/api/questoes/'),
    ('GET', '/api/atendimentos/'),
    ('GET', '/api/respostas/'),
]

# ── Endpoints N8N (exigem @api_token_required) ──────────────────────────────

N8N_ENDPOINTS = [
    ('POST', '/api/leads/registrar/'),
    ('POST', '/api/leads/atualizar/'),
    ('POST', '/api/leads/imagens/registrar/'),
    ('GET', '/api/leads/imagens/listar/?lead_id=1'),
    ('POST', '/api/leads/imagens/deletar/'),
    ('GET', '/api/leads/imagens/por-cliente/?lead_id=1'),
    ('POST', '/api/leads/imagens/validar/'),
    ('POST', '/api/prospectos/registrar/'),
    ('POST', '/api/prospectos/atualizar/'),
    ('POST', '/api/historicos/registrar/'),
    ('GET', '/api/verificar-relacionamentos/?lead_id=1'),
    ('POST', '/api/historicos/atualizar/'),
    ('POST', '/api/campanhas/detectar/'),
    # N8N atendimento
    ('POST', '/api/n8n/atendimento/iniciar/'),
    ('GET', '/api/n8n/lead/buscar/?telefone=123'),
    ('GET', '/api/n8n/fluxos/'),
]

# ── Endpoints públicos (sem auth) ───────────────────────────────────────────

PUBLIC_ENDPOINTS = [
    ('POST', '/api/cadastro/cliente/'),
    ('GET', '/api/cep/01001000/'),
]


# ============================================================================
# TESTES — Endpoints do painel
# ============================================================================

class TestPanelEndpointsRequireLogin:
    """Endpoints do painel devem redirecionar para login se não autenticado."""

    @pytest.mark.django_db
    @pytest.mark.parametrize("method,url", PANEL_ENDPOINTS)
    def test_sem_login_redireciona(self, method, url):
        client = Client()
        if method == 'GET':
            response = client.get(url)
        else:
            response = client.post(url, data='{}', content_type='application/json')

        assert response.status_code == 302, (
            f"{method} {url} deveria retornar 302 (redirect login), "
            f"retornou {response.status_code}"
        )
        assert '/login/' in response.url

    @pytest.mark.django_db
    @pytest.mark.parametrize("method,url", PANEL_ENDPOINTS)
    def test_com_login_nao_redireciona(self, method, url, user_a, config_a):
        client = Client()
        client.force_login(user_a)
        if method == 'GET':
            response = client.get(url)
        else:
            response = client.post(url, data='{}', content_type='application/json')

        assert response.status_code != 302 or '/login/' not in response.get('Location', ''), (
            f"{method} {url} redirecionou para login mesmo autenticado"
        )


# ============================================================================
# TESTES — Endpoints N8N
# ============================================================================

class TestN8NEndpointsRequireToken:
    """Endpoints N8N devem retornar 401 sem token e aceitar com token válido."""

    @pytest.mark.django_db
    @pytest.mark.parametrize("method,url", N8N_ENDPOINTS)
    def test_sem_token_retorna_401(self, method, url):
        client = Client()
        if method == 'GET':
            response = client.get(url)
        else:
            response = client.post(url, data='{}', content_type='application/json')

        assert response.status_code in (401, 503), (
            f"{method} {url} deveria retornar 401/503 sem token, "
            f"retornou {response.status_code}"
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize("method,url", N8N_ENDPOINTS)
    def test_token_invalido_retorna_401(self, method, url, settings):
        os.environ['N8N_API_TOKEN'] = 'token-correto-teste'
        client = Client()
        headers = {'HTTP_AUTHORIZATION': 'Bearer token-errado'}
        if method == 'GET':
            response = client.get(url, **headers)
        else:
            response = client.post(url, data='{}', content_type='application/json', **headers)

        assert response.status_code == 401, (
            f"{method} {url} deveria retornar 401 com token inválido, "
            f"retornou {response.status_code}"
        )
        os.environ.pop('N8N_API_TOKEN', None)

    @pytest.mark.django_db
    @pytest.mark.parametrize("method,url", N8N_ENDPOINTS)
    def test_token_valido_nao_retorna_401(self, method, url, settings):
        token = 'token-correto-teste'
        os.environ['N8N_API_TOKEN'] = token
        client = Client()
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        if method == 'GET':
            response = client.get(url, **headers)
        else:
            response = client.post(url, data='{}', content_type='application/json', **headers)

        assert response.status_code != 401, (
            f"{method} {url} retornou 401 mesmo com token válido"
        )
        os.environ.pop('N8N_API_TOKEN', None)


# ============================================================================
# TESTES — Endpoints públicos
# ============================================================================

class TestPublicEndpointsNoAuth:
    """Endpoints públicos devem funcionar sem autenticação."""

    @pytest.mark.django_db
    @pytest.mark.parametrize("method,url", PUBLIC_ENDPOINTS)
    def test_sem_auth_nao_retorna_401_nem_302(self, method, url):
        client = Client()
        if method == 'GET':
            response = client.get(url)
        else:
            response = client.post(url, data='{}', content_type='application/json')

        assert response.status_code not in (401, 302), (
            f"{method} {url} deveria ser público, "
            f"retornou {response.status_code}"
        )
