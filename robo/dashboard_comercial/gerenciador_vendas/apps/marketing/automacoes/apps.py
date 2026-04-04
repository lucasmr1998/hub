from django.apps import AppConfig


class AutomacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.marketing.automacoes'
    verbose_name = 'Automações'

    def ready(self):
        from . import signals  # noqa: F401
