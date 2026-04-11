from django.apps import AppConfig

class NotificacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notificacoes'
    verbose_name = 'Notificações'

    def ready(self):
        import apps.notificacoes.signals  # noqa: F401
