import os

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class APITokenAuthentication(BaseAuthentication):
    """Autenticação por token fixo para integrações externas (N8N, webhooks).

    Espera header: Authorization: Bearer <N8N_API_TOKEN>
    Compatível com o decorator @api_token_required existente.
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[7:]

        n8n_token = os.environ.get('N8N_API_TOKEN', '')
        webhook_token = os.environ.get('WEBHOOK_SECRET_TOKEN', '')

        if n8n_token and token == n8n_token:
            return (APIServiceUser('n8n'), 'api_token')

        if webhook_token and token == webhook_token:
            return (APIServiceUser('webhook'), 'webhook_token')

        raise AuthenticationFailed('Token inválido.')

    def authenticate_header(self, request):
        return 'Bearer'


class APIServiceUser:
    """Usuário virtual para requests autenticados por API token."""

    def __init__(self, service_name):
        self.service_name = service_name
        self.is_authenticated = True
        self.is_staff = False
        self.is_superuser = False
        self.pk = None
        self.id = None

    def __str__(self):
        return f'APIService:{self.service_name}'
