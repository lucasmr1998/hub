from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CategoriaTemplate, TemplateEmail, EnvioEmail,
    DominioRemetente, RemetenteEmail,
)


@admin.register(DominioRemetente)
class DominioRemetenteAdmin(admin.ModelAdmin):
    list_display = ('dominio', 'nome_amigavel', 'status', 'tenant', 'validado_em', 'criado_em')
    list_filter = ('status', 'tenant', 'capturar_bounces', 'capturar_complaints', 'auto_remover_lista')
    search_fields = ('dominio', 'nome_amigavel', 'resend_domain_id')
    readonly_fields = ('resend_domain_id', 'registros_dns', 'validado_em', 'ultima_verificacao', 'criado_em', 'atualizado_em')


@admin.register(RemetenteEmail)
class RemetenteEmailAdmin(admin.ModelAdmin):
    list_display = ('email_completo', 'nome_exibicao', 'dominio', 'padrao', 'ativo', 'tenant')
    list_filter = ('ativo', 'padrao', 'dominio', 'tenant')
    search_fields = ('local_part', 'nome_exibicao', 'reply_to')


@admin.register(CategoriaTemplate)
class CategoriaTemplateAdmin(admin.ModelAdmin):
    list_display = ('nome', 'icone', 'ordem', 'tenant')
    list_filter = ('tenant',)
    search_fields = ('nome',)
    ordering = ('ordem', 'nome')


@admin.register(TemplateEmail)
class TemplateEmailAdmin(admin.ModelAdmin):
    list_display = ('nome', 'assunto', 'status_badge', 'categoria', 'total_blocos', 'total_envios', 'criado_por', 'atualizado_em')
    list_filter = ('status', 'eh_modelo_base', 'categoria', 'tenant')
    search_fields = ('nome', 'assunto', 'descricao')
    readonly_fields = ('html_compilado', 'criado_em', 'atualizado_em')
    fieldsets = (
        ('Identificação', {'fields': ('nome', 'descricao', 'assunto', 'categoria', 'status')}),
        ('Conteúdo', {'fields': ('config_json', 'blocos_json', 'html_compilado')}),
        ('Configurações', {'fields': ('eh_modelo_base', 'thumbnail')}),
        ('Metadata', {'fields': ('tenant', 'criado_por', 'criado_em', 'atualizado_em'), 'classes': ('collapse',)}),
    )

    def status_badge(self, obj):
        cores = {'ativo': '#16a34a', 'rascunho': '#f59e0b', 'arquivado': '#6b7280'}
        cor = cores.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{}</span>',
            cor, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(EnvioEmail)
class EnvioEmailAdmin(admin.ModelAdmin):
    list_display = ('email_destino', 'assunto_renderizado', 'template', 'status_badge', 'enviado_em', 'aberto_em', 'clicado_em')
    list_filter = ('status', 'enviado_em', 'tenant')
    search_fields = ('email_destino', 'assunto_renderizado')
    readonly_fields = ('tracking_id', 'enviado_em', 'aberto_em', 'clicado_em')
    raw_id_fields = ('lead', 'template', 'automacao')

    def status_badge(self, obj):
        cores = {'enviado': '#3b82f6', 'aberto': '#16a34a', 'clicado': '#8b5cf6', 'erro': '#ef4444', 'bounce': '#f59e0b'}
        cor = cores.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">{}</span>',
            cor, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
