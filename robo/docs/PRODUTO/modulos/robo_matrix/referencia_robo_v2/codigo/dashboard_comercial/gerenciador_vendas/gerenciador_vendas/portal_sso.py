"""
Middleware SSO para integracao com o Portal Megalink.

Quando o portal redireciona um usuario para este sistema via POST com
`portal_token`, este middleware intercepta, valida o token na API do portal,
cria/atualiza o usuario local e faz login automatico.

Configuracao necessaria no settings.py:
    PORTAL_URL = 'http://localhost:8000'
    PORTAL_SECRET_KEY = 'chave-secreta-do-modulo'
"""
import json
import logging
import urllib.request
import urllib.error

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden, HttpResponseRedirect

logger = logging.getLogger(__name__)


class PortalSSOMiddleware:
    """
    Intercepta requests POST com `portal_token` e autentica o usuario
    via API do Portal Megalink.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # So intercepta POST com portal_token
        if request.method == 'POST' and 'portal_token' in request.POST:
            return self._handle_sso(request)
        return self.get_response(request)

    def _get_client_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def _redirect_portal_com_erro(self, portal_url_publica, motivo):
        """Volta o usuario pro portal com mensagem em vez de mostrar 403 plano."""
        from urllib.parse import quote
        return HttpResponseRedirect(f"{portal_url_publica}/?sso_error={quote(motivo)}")

    def _handle_sso(self, request):
        token = request.POST.get('portal_token', '')
        # PORTAL_URL = interno (server-to-server, evita Cloudflare)
        # PORTAL_URL_PUBLICA = HTTPS publico (redirect ao browser)
        portal_url = getattr(settings, 'PORTAL_URL', 'http://localhost:8000')
        portal_url_publica = getattr(settings, 'PORTAL_URL_PUBLICA', portal_url)
        secret_key = getattr(settings, 'PORTAL_SECRET_KEY', '')

        if not secret_key:
            logger.error('PORTAL_SECRET_KEY nao configurada no settings.py')
            return self._redirect_portal_com_erro(portal_url_publica, 'SSO nao configurado no modulo.')

        # Chamar API do portal para validar token (uso interno)
        api_url = f"{portal_url}/api/validar-token/"
        payload = json.dumps({
            'token': token,
            'secret_key': secret_key,
            'client_ip': self._get_client_ip(request),
        }).encode('utf-8')

        try:
            req = urllib.request.Request(
                api_url,
                data=payload,
                headers={'Content-Type': 'application/json'},
            )
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body_raw = e.read().decode('utf-8', errors='replace')
            try:
                body = json.loads(body_raw)
                motivo_real = body.get('error', body_raw)
            except (json.JSONDecodeError, ValueError):
                motivo_real = body_raw
            logger.warning(
                f'Portal SSO rejeitou token (HTTP {e.code}): {motivo_real} | '
                f'IP visto pelo modulo: {self._get_client_ip(request)}'
            )
            return self._redirect_portal_com_erro(portal_url_publica, motivo_real)
        except Exception as e:
            logger.error(f'Erro ao validar token no portal: {e}')
            return self._redirect_portal_com_erro(portal_url_publica, 'Portal indisponivel. Tente novamente.')

        if not data.get('valid'):
            return self._redirect_portal_com_erro(portal_url_publica, 'Token invalido.')

        # Criar ou atualizar usuario local.
        # Flags de admin sao elevadas pelo portal mas NUNCA rebaixadas aqui:
        # um superuser concedido localmente (admin so deste projeto) se mantem
        # mesmo que a conta no portal nao seja superuser.
        user_data = data['user']
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'email': user_data.get('email', ''),
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
            },
        )
        user.email = user_data.get('email', user.email)
        user.first_name = user_data.get('first_name', user.first_name)
        user.last_name = user_data.get('last_name', user.last_name)
        user.is_staff = user.is_staff or user_data.get('is_staff', False)
        user.is_superuser = user.is_superuser or user_data.get('is_superuser', False)
        if created:
            # Senha inutilizavel — login so via portal
            user.set_unusable_password()
            logger.info(f'Usuario criado via SSO: {user.username}')
        user.save()

        # Login automatico
        login(request, user)
        logger.info(f'SSO login: {user.username} via portal')

        # Redirecionar para a mesma URL (agora com sessao, sem token)
        return HttpResponseRedirect(request.path)
