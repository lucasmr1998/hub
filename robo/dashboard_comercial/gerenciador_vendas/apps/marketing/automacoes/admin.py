from django.contrib import admin
from .models import RegraAutomacao, CondicaoRegra, AcaoRegra, LogExecucao


class CondicaoInline(admin.TabularInline):
    model = CondicaoRegra
    extra = 0
    fields = ('campo', 'operador', 'valor', 'ordem')


class AcaoInline(admin.TabularInline):
    model = AcaoRegra
    extra = 0
    fields = ('tipo', 'configuracao', 'ordem', 'delay_ativo', 'delay_valor', 'delay_unidade')


@admin.register(RegraAutomacao)
class RegraAutomacaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'evento', 'ativa', 'total_execucoes', 'taxa_sucesso', 'data_criacao')
    list_filter = ('ativa', 'evento')
    search_fields = ('nome', 'descricao')
    inlines = [CondicaoInline, AcaoInline]


@admin.register(LogExecucao)
class LogExecucaoAdmin(admin.ModelAdmin):
    list_display = ('regra', 'acao', 'status', 'data_execucao')
    list_filter = ('status', 'regra')
    readonly_fields = ('regra', 'acao', 'status', 'evento_dados', 'resultado', 'data_execucao', 'data_agendada')
