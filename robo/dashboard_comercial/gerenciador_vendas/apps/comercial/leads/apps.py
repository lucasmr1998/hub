from django.apps import AppConfig

class LeadsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.comercial.leads'
    verbose_name = 'Comercial > Leads'

    def ready(self):
        from . import signals  # noqa: F401
