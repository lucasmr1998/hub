from django.apps import AppConfig


class CronConfig(AppConfig):
    """
    Cron — dispatcher centralizado de jobs periodicos do Hubtrix.

    Cross-tenant. 1 service de cron no Easypanel (hub-dispatcher) roda
    `python manage.py dispatcher_cron` a cada 1min e dispara os CronJob ativos
    cujo schedule cron bate com o minuto atual.

    Models:
      - CronJob: declara um job (command + schedule + args + ativo).
      - ExecucaoCron: log de cada execucao (stdout, stderr, status, duracao).

    Acesso: somente Aurora Admin (Aurora HQ).
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cron'
    verbose_name = 'Cron Dispatcher'

    def ready(self):
        # Importa signals (alertar_quando_cron_falha) — tarefa Workspace #152
        from apps.cron import signals  # noqa: F401
