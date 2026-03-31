from django.apps import AppConfig


class VendasWebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vendas_web'
    verbose_name = '📊 Gestão Comercial'

    def ready(self):
        # Signals migrados para apps/comercial/leads/signals.py e apps/comercial/cadastro/signals.py
        # from . import signals  # noqa: F401
        pass
