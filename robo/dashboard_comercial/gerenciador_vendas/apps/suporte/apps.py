from django.apps import AppConfig


class SuporteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.suporte'
    verbose_name = 'Suporte'

    def ready(self):
        # Registra signals (regeracao de embedding em ArtigoConhecimento)
        from . import signals  # noqa: F401
