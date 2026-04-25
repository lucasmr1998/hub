from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class SistemaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sistema'
    verbose_name = 'Sistema'

    def ready(self):
        from . import signals  # noqa: F401

        # Guard contra a regressao do bug de encriptacao: SECRET_KEY tem que
        # estar setada e nao pode ser default inseguro em producao. Se for,
        # qualquer dado encriptado (API tokens, senhas) vira lixo no proximo
        # boot e o painel passa a mandar credenciais invalidas pras APIs.
        if not getattr(settings, 'SECRET_KEY', None):
            raise ImproperlyConfigured(
                'SECRET_KEY nao configurada. EncryptedFields dependem dela '
                'pra encriptar/decriptar tokens de API. Defina antes de subir.'
            )
        if not getattr(settings, 'DEBUG', False):
            inseguros = ('dev-local-insecure-key-only-for-testing', 'changeme', '')
            if settings.SECRET_KEY in inseguros or len(settings.SECRET_KEY) < 32:
                raise ImproperlyConfigured(
                    'SECRET_KEY de producao invalida (default/curta). '
                    'Defina uma chave forte de >=32 chars em producao — caso '
                    'contrario tokens de API encriptados ficarao ilegiveis.'
                )
