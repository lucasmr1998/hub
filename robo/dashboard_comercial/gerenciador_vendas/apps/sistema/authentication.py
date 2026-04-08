import os
import logging

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


class APITokenAuthentication(BaseAuthentication):
    """Autenticacao por token para integracoes externas (N8N, webhooks).

    Espera header: Authorization: Bearer <token>

    Fluxo de validacao:
    1. Busca token nas integracoes ativas (por tenant) — identifica o tenant
    2. Fallback: compara com N8N_API_TOKEN global (env var) — sem tenant
    3. Fallback: compara com WEBHOOK_SECRET_TOKEN global (env var)
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[7:].strip()
        if not token:
            return None

        # 1. Buscar token nas integracoes (por tenant)
        try:
            from apps.integracoes.models import IntegracaoAPI
            integracao = IntegracaoAPI.all_tenants.filter(
                api_token=token,
                ativa=True,
            ).select_related('tenant').first()

            if integracao and integracao.tenant:
                # Setar tenant no request para TenantManager funcionar
                request.tenant = integracao.tenant
                from apps.sistema.middleware import _thread_locals
                _thread_locals.tenant = integracao.tenant
                return (APIServiceUser('n8n', tenant=integracao.tenant), 'api_token')
        except Exception as e:
            logger.error("Erro ao buscar token no banco: %s", e, exc_info=True)

        # 2. Fallback: token global N8N
        n8n_token = os.environ.get('N8N_API_TOKEN', '')
        if n8n_token and token == n8n_token:
            return (APIServiceUser('n8n'), 'api_token')

        # 3. Fallback: token global webhook
        webhook_token = os.environ.get('WEBHOOK_SECRET_TOKEN', '')
        if webhook_token and token == webhook_token:
            return (APIServiceUser('webhook'), 'webhook_token')

        raise AuthenticationFailed('Token invalido.')

    def authenticate_header(self, request):
        return 'Bearer'


class APIServiceUser:
    """Usuario virtual para requests autenticados por API token."""

    def __init__(self, service_name, tenant=None):
        self.service_name = service_name
        self.tenant = tenant
        self.username = f'api:{service_name}'
        self.is_authenticated = True
        self.is_staff = False
        self.is_superuser = False
        self.pk = None
        self.id = None

    def __str__(self):
        if self.tenant:
            return f'APIService:{self.service_name}:{self.tenant.nome}'
        return f'APIService:{self.service_name}'
