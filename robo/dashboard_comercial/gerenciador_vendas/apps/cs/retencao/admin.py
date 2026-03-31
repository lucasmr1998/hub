from django.contrib import admin
from .models import ScoreCliente, AlertaChurn, AcaoRetencao


@admin.register(ScoreCliente)
class ScoreClienteAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'score', 'ultima_atualizacao')
    list_filter = ('score',)
    readonly_fields = ('ultima_atualizacao',)


@admin.register(AlertaChurn)
class AlertaChurnAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'tipo', 'severidade', 'resolvido', 'data_criacao')
    list_filter = ('tipo', 'severidade', 'resolvido')
    readonly_fields = ('data_criacao',)


@admin.register(AcaoRetencao)
class AcaoRetencaoAdmin(admin.ModelAdmin):
    list_display = ('alerta', 'tipo_acao', 'responsavel', 'executada', 'data_criacao')
    list_filter = ('tipo_acao', 'executada')
    readonly_fields = ('data_criacao',)
