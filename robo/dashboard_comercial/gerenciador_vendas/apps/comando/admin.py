"""
Admin do Comando — registra os 11 models pra acesso interno via /admin/.
Models são DORMENTES na fase 1; admin é a única forma de visualizar/limpar dados.
"""
from django.contrib import admin
from apps.comando.models import (
    Agente, ToolAgente, LogTool, MensagemChat,
    Reuniao, MensagemReuniao,
    Automacao, Alerta, Proposta,
    FAQCategoria, FAQItem,
)


@admin.register(Agente)
class AgenteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'time', 'modelo', 'ativo', 'ordem')
    list_filter = ('time', 'ativo', 'modelo')
    search_fields = ('nome', 'slug', 'descricao')
    ordering = ('ordem', 'nome')


@admin.register(ToolAgente)
class ToolAgenteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'tipo', 'ativo', 'ordem')
    list_filter = ('tipo', 'ativo')
    search_fields = ('nome', 'slug', 'descricao')
    ordering = ('ordem', 'nome')


@admin.register(LogTool)
class LogToolAdmin(admin.ModelAdmin):
    list_display = ('tool_slug', 'agente', 'sucesso', 'tempo_ms', 'criado_em')
    list_filter = ('sucesso', 'tool_slug')
    search_fields = ('tool_slug', 'resultado')
    ordering = ('-criado_em',)
    readonly_fields = ('criado_em',)


@admin.register(MensagemChat)
class MensagemChatAdmin(admin.ModelAdmin):
    list_display = ('agente', 'role', 'criado_em')
    list_filter = ('role', 'agente')
    ordering = ('-criado_em',)
    readonly_fields = ('criado_em',)


@admin.register(Reuniao)
class ReuniaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativa', 'total_mensagens', 'criado_em')
    list_filter = ('ativa',)
    search_fields = ('nome', 'descricao')
    ordering = ('-criado_em',)


@admin.register(MensagemReuniao)
class MensagemReuniaoAdmin(admin.ModelAdmin):
    list_display = ('reuniao', 'tipo', 'agente_nome', 'criado_em')
    list_filter = ('tipo',)
    search_fields = ('agente_nome', 'conteudo')
    ordering = ('-criado_em',)


@admin.register(Automacao)
class AutomacaoAdmin(admin.ModelAdmin):
    list_display = ('modo', 'tool', 'agente', 'intervalo_horas', 'status', 'ativo', 'ultima_execucao')
    list_filter = ('modo', 'status', 'ativo')
    ordering = ('-criado_em',)


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'severidade', 'lido', 'resolvido', 'criado_em')
    list_filter = ('tipo', 'severidade', 'lido', 'resolvido')
    search_fields = ('titulo', 'descricao')
    ordering = ('-criado_em',)


@admin.register(Proposta)
class PropostaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'agente', 'prioridade', 'status', 'criado_em')
    list_filter = ('prioridade', 'status', 'agente')
    search_fields = ('titulo', 'descricao')
    ordering = ('-criado_em',)


@admin.register(FAQCategoria)
class FAQCategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'ordem', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('nome', 'slug')
    ordering = ('ordem', 'nome')


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ('pergunta_truncada', 'categoria', 'ordem', 'gerado_por_ia', 'ativo')
    list_filter = ('categoria', 'gerado_por_ia', 'ativo')
    search_fields = ('pergunta', 'resposta')
    ordering = ('categoria', 'ordem')

    def pergunta_truncada(self, obj):
        return obj.pergunta[:80]
    pergunta_truncada.short_description = 'Pergunta'
