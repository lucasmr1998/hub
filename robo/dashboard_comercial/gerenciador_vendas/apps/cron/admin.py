"""Registro no Django admin classico (alem do painel customizado em aurora-admin)."""
from django.contrib import admin

from .models import CronJob, ExecucaoCron


@admin.register(CronJob)
class CronJobAdmin(admin.ModelAdmin):
    list_display = ('nome', 'command', 'schedule', 'ativo', 'last_status', 'last_run_at')
    list_filter = ('ativo', 'last_status')
    search_fields = ('nome', 'command')


@admin.register(ExecucaoCron)
class ExecucaoCronAdmin(admin.ModelAdmin):
    list_display = ('cron_job', 'inicio', 'status', 'duracao_segundos', 'disparado_por')
    list_filter = ('status', 'cron_job')
    readonly_fields = ('cron_job', 'inicio', 'fim', 'duracao_segundos', 'status',
                       'return_code', 'stdout', 'stderr', 'disparado_por')
