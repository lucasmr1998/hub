from django.apps import AppConfig


class ComandoConfig(AppConfig):
    """
    Comando — operação interna da Hubtrix (mono-tenant).

    Camada de IA (agentes, tools, automações, propostas, alertas, FAQ)
    importada do megaroleta legado. DORMENTE na fase 1: só schema +
    dados preservados, sem UI ativa. Acessível via Django admin + shell.

    Ressuscitação prevista pra fase 3, com decisão de produto sobre
    multi-tenant antes (hoje é mono-tenant — Hubtrix-only).
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.comando'
    verbose_name = 'Comando (operação interna)'
