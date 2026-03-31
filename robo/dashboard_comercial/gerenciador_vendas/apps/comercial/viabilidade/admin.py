from django.contrib import admin
from django.utils.html import format_html

from apps.comercial.viabilidade.models import CidadeViabilidade


@admin.register(CidadeViabilidade)
class CidadeViabilidadeAdmin(admin.ModelAdmin):
    list_display = (
        'cidade_estado_badge', 'cep_display', 'bairro_display',
        'observacao_curta', 'ativo_badge', 'data_criacao',
    )
    list_filter = ('estado', 'ativo', 'data_criacao')
    search_fields = ('cidade', 'cep', 'bairro', 'estado')
    ordering = ('estado', 'cidade', 'cep')
    list_per_page = 50
    readonly_fields = ('data_criacao', 'data_atualizacao')

    fieldsets = (
        ('📍 Localização', {
            'fields': ('cidade', 'estado', 'bairro', 'cep'),
            'description': (
                'Informe a cidade e estado (obrigatório). '
                'CEP e bairro são opcionais — se não informados, '
                'toda a cidade é considerada com viabilidade.'
            ),
        }),
        ('📝 Detalhes', {
            'fields': ('observacao', 'ativo'),
        }),
        ('📊 Controle', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',),
        }),
    )

    def cidade_estado_badge(self, obj):
        return format_html(
            '<strong style="color:#1F3D59;">{}</strong>'
            ' <span style="background:#eef3f7;color:#1F3D59;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:700;">{}</span>',
            obj.cidade, obj.estado,
        )
    cidade_estado_badge.short_description = 'Cidade / UF'
    cidade_estado_badge.admin_order_field = 'cidade'

    def cep_display(self, obj):
        if obj.cep:
            return format_html(
                '<span style="font-family:monospace;background:#f3f4f6;'
                'padding:2px 7px;border-radius:6px;font-size:12px;">{}</span>',
                obj.cep,
            )
        return format_html('<span style="color:#aaa;font-size:11px;">Cidade inteira</span>')
    cep_display.short_description = 'CEP'
    cep_display.admin_order_field = 'cep'

    def bairro_display(self, obj):
        return obj.bairro or format_html('<span style="color:#aaa;">—</span>')
    bairro_display.short_description = 'Bairro'

    def observacao_curta(self, obj):
        if obj.observacao:
            txt = obj.observacao[:60]
            return txt + '…' if len(obj.observacao) > 60 else txt
        return format_html('<span style="color:#aaa;">—</span>')
    observacao_curta.short_description = 'Observação'

    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:3px 10px;'
                'border-radius:12px;font-size:11px;font-weight:700;">✔ Ativo</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#991b1b;padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:700;">✘ Inativo</span>'
        )
    ativo_badge.short_description = 'Status'
    ativo_badge.admin_order_field = 'ativo'

    actions = ['ativar_registros', 'desativar_registros']

    def ativar_registros(self, request, queryset):
        n = queryset.update(ativo=True)
        self.message_user(request, f'{n} registro(s) ativado(s).')
    ativar_registros.short_description = 'Ativar selecionados'

    def desativar_registros(self, request, queryset):
        n = queryset.update(ativo=False)
        self.message_user(request, f'{n} registro(s) desativado(s).')
    desativar_registros.short_description = 'Desativar selecionados'
