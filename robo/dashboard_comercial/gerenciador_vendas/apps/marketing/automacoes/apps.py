from django.apps import AppConfig


class AutomacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.marketing.automacoes'
    verbose_name = 'Automações'

    def ready(self):
        # Signals de domínio RELOCADOS pra apps.automacao.signals_dominio (motor em
        # aposentadoria). Não registrar aqui — senão os eventos disparam 2x.
        pass
