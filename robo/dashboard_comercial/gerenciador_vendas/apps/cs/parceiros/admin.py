from django.contrib import admin
from apps.cs.parceiros.models import Parceiro, CupomDesconto, ResgateCupom

@admin.register(Parceiro)
class ParceiroAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo', 'data_cadastro']
    list_filter = ['ativo']
    search_fields = ['nome']

@admin.register(CupomDesconto)
class CupomDescontoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'parceiro', 'modalidade', 'tipo_desconto', 'valor_desconto', 'ativo']
    list_filter = ['ativo', 'modalidade', 'parceiro']
    search_fields = ['titulo', 'codigo']

@admin.register(ResgateCupom)
class ResgateCupomAdmin(admin.ModelAdmin):
    list_display = ['membro', 'cupom', 'codigo_unico', 'status', 'data_resgate']
    list_filter = ['status']
    search_fields = ['codigo_unico', 'membro__nome']
