from django.apps import AppConfig


class IaValidadorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ia_validador'
    verbose_name = 'IA Validador'

    def ready(self):
        from . import signals  # noqa: F401 — registra signal de invalidação de cache
