from django.apps import AppConfig


class IntegracoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integracoes'
    verbose_name = '🔗 Integrações'

    def ready(self):
        from . import signals  # noqa: F401
