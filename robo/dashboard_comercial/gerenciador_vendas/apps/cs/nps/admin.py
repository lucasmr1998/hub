from django.contrib import admin
from .models import ConfiguracaoNPS, PesquisaNPS


@admin.register(ConfiguracaoNPS)
class ConfiguracaoNPSAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'periodicidade_dias', 'canal_envio', 'ativo')
    list_filter = ('ativo', 'canal_envio')


@admin.register(PesquisaNPS)
class PesquisaNPSAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'nota', 'categoria', 'respondida', 'data_envio')
    list_filter = ('categoria', 'respondida', 'canal_resposta')
    search_fields = ('comentario',)
    readonly_fields = ('data_envio', 'data_resposta')
