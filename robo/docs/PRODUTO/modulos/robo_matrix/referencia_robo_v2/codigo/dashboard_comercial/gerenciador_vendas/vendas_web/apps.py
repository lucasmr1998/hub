from django.apps import AppConfig


class VendasWebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vendas_web'
    verbose_name = '📊 Gestão Comercial'

    def ready(self):
        from . import signals  # noqa: F401
        # Conecta o signal post_save de NewService aqui (não no decorator
        # @receiver) porque NewService é definido em models.py APÓS o
        # import do signals.py — circular import se tentarmos importar
        # NewService diretamente em signals.py em tempo de carga.
        from django.db.models.signals import post_save
        from .models import NewService
        post_save.connect(
            signals.disparar_sync_matrix_ao_finalizar,
            sender=NewService,
            dispatch_uid='newservice_sync_matrix_on_finalize',
        )
