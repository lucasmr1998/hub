from django.apps import AppConfig


class VendasWebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vendas_web'
    verbose_name = '📊 Gestão Comercial'

    def ready(self):
        from . import signals  # noqa: F401
