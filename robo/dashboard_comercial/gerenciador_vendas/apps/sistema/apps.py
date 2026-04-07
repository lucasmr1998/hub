from django.apps import AppConfig


class SistemaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sistema'
    verbose_name = 'Sistema'

    def ready(self):
        from . import signals  # noqa: F401
