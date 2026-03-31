from django.contrib import admin
from .models import ModeloCarteirinha, RegraAtribuicao, CarteirinhaMembro

@admin.register(ModeloCarteirinha)
class ModeloCarteirinhaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo', 'data_criacao']

@admin.register(RegraAtribuicao)
class RegraAtribuicaoAdmin(admin.ModelAdmin):
    list_display = ['modelo', 'tipo', 'prioridade', 'ativo']

@admin.register(CarteirinhaMembro)
class CarteirinhaMembroAdmin(admin.ModelAdmin):
    list_display = ['membro', 'modelo', 'data_emissao', 'ativo']
