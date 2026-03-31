from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.comercial.crm'
    verbose_name = 'Comercial > CRM'

    def ready(self):
        from . import signals  # noqa: F401
