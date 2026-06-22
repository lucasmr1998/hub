from django.apps import AppConfig


class AutomacaoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.automacao'
    verbose_name = 'Automação'

    def ready(self):
        # Importa os nós pra popular o REGISTRY no boot.
        from . import nodes  # noqa: F401
        # Gancho do inbox (retoma execução por resposta).
        from . import signals  # noqa: F401
        # Self-check de boot (avisa se a rota da automação sumir do urls.py).
        from . import checks  # noqa: F401
