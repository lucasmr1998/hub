"""
Testes de acesso aos módulos por tipo de usuário.

Verifica que:
- Usuário com módulo habilitado acessa as páginas do módulo
- Usuário sem login é redirecionado
- Páginas críticas de cada módulo carregam sem erro
"""
import pytest
from django.test import Client


MODULE_PAGES = {
    'dashboard': [
        '/dashboard1/',
    ],
    'comercial': [
        '/leads/',
    ],
    'cs': [
        '/cs/clube/dashboard/',
    ],
}


@pytest.mark.django_db
class TestModuleAccessWithLogin:
    """Usuário logado com tenant ativo deve acessar todos os módulos habilitados."""

    def test_dashboard_acessivel(self, client, user_a, config_a):
        client.force_login(user_a)
        response = client.get('/dashboard1/')
        assert response.status_code == 200, (
            f"Dashboard retornou {response.status_code} para usuário logado"
        )

    def test_leads_acessivel(self, client, user_a, config_a):
        client.force_login(user_a)
        response = client.get('/leads/')
        assert response.status_code == 200, (
            f"Leads retornou {response.status_code} para usuário logado"
        )

    def test_cs_clube_acessivel(self, client, user_a, config_a):
        client.force_login(user_a)
        response = client.get('/cs/clube/dashboard/')
        assert response.status_code == 200, (
            f"CS Clube retornou {response.status_code} para usuário logado. "
            f"Módulo CS não deve exigir is_staff."
        )

    def test_cs_parceiros_acessivel(self, client, user_a, config_a):
        client.force_login(user_a)
        response = client.get('/cs/parceiros/dashboard/parceiros/')
        assert response.status_code == 200, (
            f"CS Parceiros retornou {response.status_code} para usuário logado"
        )

    def test_cs_indicacoes_acessivel(self, client, user_a, config_a):
        client.force_login(user_a)
        response = client.get('/cs/indicacoes/dashboard/indicacoes/')
        assert response.status_code == 200, (
            f"CS Indicações retornou {response.status_code} para usuário logado"
        )

    def test_cs_carteirinha_acessivel(self, client, user_a, config_a):
        client.force_login(user_a)
        response = client.get('/cs/carteirinha/dashboard/carteirinha/')
        assert response.status_code == 200, (
            f"CS Carteirinha retornou {response.status_code} para usuário logado"
        )


@pytest.mark.django_db
class TestModuleAccessWithoutLogin:
    """Sem login, todos os módulos devem redirecionar para login."""

    @pytest.mark.parametrize("url", [
        '/dashboard1/',
        '/leads/',
        '/cs/clube/dashboard/',
        '/cs/parceiros/dashboard/parceiros/',
        '/cs/indicacoes/dashboard/indicacoes/',
        '/cs/carteirinha/dashboard/carteirinha/',
        '/configuracoes/',
    ])
    def test_redireciona_para_login(self, client, url):
        response = client.get(url)
        assert response.status_code == 302, (
            f"{url} deveria redirecionar sem login, retornou {response.status_code}"
        )
