from django.contrib import admin

from .models import Dashboard, Widget


class WidgetInline(admin.TabularInline):
    model = Widget
    extra = 0
    fields = ('titulo', 'data_source', 'visualizacao', 'ordem')
    readonly_fields = ('criado_em',)


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tenant', 'criado_por', 'compartilhado', 'ordem', 'atualizado_em')
    list_filter = ('compartilhado', 'tenant')
    search_fields = ('nome', 'descricao')
    inlines = [WidgetInline]
    readonly_fields = ('criado_em', 'atualizado_em')


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'dashboard', 'data_source', 'visualizacao', 'ordem')
    list_filter = ('data_source', 'visualizacao', 'dashboard__tenant')
    search_fields = ('titulo', 'descricao')
    readonly_fields = ('criado_em', 'atualizado_em')
