from django.contrib import admin
from .models import Indicacao

@admin.register(Indicacao)
class IndicacaoAdmin(admin.ModelAdmin):
    list_display = ['membro_indicador', 'nome_indicado', 'telefone_indicado', 'status', 'pontos_creditados', 'data_indicacao']
    list_filter = ['status', 'pontos_creditados']
    search_fields = ['nome_indicado', 'telefone_indicado', 'membro_indicador__nome']
