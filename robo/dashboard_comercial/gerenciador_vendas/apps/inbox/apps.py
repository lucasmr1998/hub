from django.apps import AppConfig


class InboxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inbox'
    verbose_name = 'Inbox'

    def ready(self):
        import apps.inbox.signals  # noqa: F401
