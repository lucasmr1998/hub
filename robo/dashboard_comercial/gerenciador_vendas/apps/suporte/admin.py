from django.contrib import admin
from .models import (
    CategoriaTicket, SLAConfig, Ticket, ComentarioTicket,
    CategoriaConhecimento, ArtigoConhecimento,
)


class ComentarioInline(admin.TabularInline):
    model = ComentarioTicket
    extra = 0
    readonly_fields = ['data_criacao']


@admin.register(CategoriaTicket)
class CategoriaTicketAdmin(admin.ModelAdmin):
    list_display = ['nome', 'slug', 'icone', 'ordem', 'ativo']
    list_editable = ['ordem', 'ativo']
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(SLAConfig)
class SLAConfigAdmin(admin.ModelAdmin):
    list_display = ['plano_tier', 'tempo_primeira_resposta_horas', 'tempo_resolucao_horas', 'ativo']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['numero', 'titulo', 'status', 'prioridade', 'categoria', 'solicitante', 'atendente', 'data_abertura']
    list_filter = ['status', 'prioridade', 'categoria']
    search_fields = ['titulo', 'descricao', 'numero']
    readonly_fields = ['numero', 'data_abertura', 'data_primeira_resposta', 'data_resolucao', 'data_fechamento']
    inlines = [ComentarioInline]


@admin.register(ComentarioTicket)
class ComentarioTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'autor', 'interno', 'data_criacao']
    list_filter = ['interno']


@admin.register(CategoriaConhecimento)
class CategoriaConhecimentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'slug', 'icone', 'ordem', 'ativo']
    list_editable = ['ordem', 'ativo']
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(ArtigoConhecimento)
class ArtigoConhecimentoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'categoria', 'publicado', 'destaque', 'visualizacoes', 'atualizado_em']
    list_filter = ['publicado', 'destaque', 'categoria']
    search_fields = ['titulo', 'conteudo', 'tags']
    prepopulated_fields = {'slug': ('titulo',)}
