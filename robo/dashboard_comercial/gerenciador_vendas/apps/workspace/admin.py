"""
Admin do Workspace — interface básica pra debug e gestão direta.
A UI principal vai ser via /workspace/ com layout_app.html (DS Hubtrix).
"""
from django.contrib import admin

from apps.workspace.models import (
    Projeto, Etapa, Tarefa, Nota,
    Documento, PastaDocumento, AnexoDocumento,
)


@admin.register(AnexoDocumento)
class AnexoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nome_original', 'documento', 'tipo', 'gerado_por_ia', 'modelo_ia', 'criado_em')
    list_filter = ('tipo', 'gerado_por_ia', 'tenant')
    search_fields = ('nome_original', 'documento__titulo', 'prompt_ia')
    readonly_fields = ('arquivo', 'mime_type', 'tamanho_bytes', 'criado_em')


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tenant', 'status', 'prioridade', 'responsavel', 'ativo', 'criado_em')
    list_filter = ('status', 'prioridade', 'ativo')
    search_fields = ('nome', 'descricao', 'objetivo')
    autocomplete_fields = ('responsavel',)
    ordering = ('-criado_em',)


@admin.register(Etapa)
class EtapaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'projeto', 'ordem', 'data_inicio', 'data_fim')
    list_filter = ('projeto',)
    search_fields = ('nome', 'descricao')
    ordering = ('projeto', 'ordem')


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'projeto', 'status', 'prioridade', 'responsavel', 'data_limite')
    list_filter = ('status', 'prioridade', 'projeto')
    search_fields = ('titulo', 'descricao')
    autocomplete_fields = ('responsavel', 'projeto', 'etapa')
    ordering = ('-criado_em',)


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ('texto_truncado', 'tarefa', 'autor', 'criado_em')
    search_fields = ('texto',)
    ordering = ('-criado_em',)

    def texto_truncado(self, obj):
        return obj.texto[:60]
    texto_truncado.short_description = 'Texto'


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria', 'pasta', 'tenant', 'visivel_agentes', 'atualizado_em')
    list_filter = ('categoria', 'visivel_agentes', 'pasta')
    search_fields = ('titulo', 'conteudo', 'resumo')
    prepopulated_fields = {'slug': ('titulo',)}
    ordering = ('-atualizado_em',)


@admin.register(PastaDocumento)
class PastaDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tenant', 'pai', 'ordem')
    list_filter = ('pai',)
    search_fields = ('nome',)
    prepopulated_fields = {'slug': ('nome',)}
    ordering = ('ordem', 'nome')
