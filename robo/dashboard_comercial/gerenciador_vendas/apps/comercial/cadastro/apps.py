from django.apps import AppConfig


class CadastroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.comercial.cadastro'
    verbose_name = 'Comercial > Cadastro'

    def ready(self):
        from . import signals  # noqa: F401
