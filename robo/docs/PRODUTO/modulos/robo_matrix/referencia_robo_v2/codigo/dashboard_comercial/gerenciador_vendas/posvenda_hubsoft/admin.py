from django.contrib import admin

from .models import ExecucaoHubsoft, CapturaAPI


@admin.register(ExecucaoHubsoft)
class ExecucaoHubsoftAdmin(admin.ModelAdmin):
    list_display = ('id', 'processo', 'registro_id', 'executor', 'status',
                    'dry_run', 'tentativa_fallback', 'duracao_ms', 'etapa', 'criado_em')
    list_filter = ('processo', 'executor', 'status', 'dry_run', 'tentativa_fallback')
    search_fields = ('registro_id', 'erro', 'etapa')
    readonly_fields = [f.name for f in ExecucaoHubsoft._meta.fields]
    date_hierarchy = 'criado_em'

    def has_add_permission(self, request):
        return False


@admin.register(CapturaAPI)
class CapturaAPIAdmin(admin.ModelAdmin):
    list_display = ('id', 'processo', 'registro_id', 'metodo', 'endpoint',
                    'status_code', 'criado_em')
    list_filter = ('processo', 'metodo', 'status_code')
    search_fields = ('endpoint', 'registro_id')
    readonly_fields = [f.name for f in CapturaAPI._meta.fields]
    date_hierarchy = 'criado_em'

    def has_add_permission(self, request):
        return False
