from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from apps.marketing.campanhas.models import (
    CampanhaTrafego,
    DeteccaoCampanha,
)


@admin.register(CampanhaTrafego)
class CampanhaTrafegoAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'codigo', 'palavra_chave', 'plataforma',
        'ativa', 'contador_deteccoes', 'total_leads_display',
        'esta_no_periodo_display', 'criado_em'
    ]
    list_filter = ['ativa', 'plataforma', 'tipo_trafego', 'data_inicio', 'data_fim']
    search_fields = ['nome', 'codigo', 'palavra_chave', 'descricao']
    readonly_fields = [
        'contador_deteccoes', 'ultima_deteccao', 'criado_em',
        'atualizado_em', 'criado_por', 'estatisticas_display'
    ]

    fieldsets = (
        ('Identificação', {
            'fields': ('nome', 'codigo', 'descricao')
        }),
        ('Palavra-chave', {
            'fields': ('palavra_chave', 'tipo_match', 'case_sensitive')
        }),
        ('Classificação', {
            'fields': ('plataforma', 'tipo_trafego', 'prioridade', 'ativa')
        }),
        ('Período', {
            'fields': ('data_inicio', 'data_fim')
        }),
        ('Comercial', {
            'fields': ('url_destino', 'orcamento', 'meta_leads')
        }),
        ('Estatísticas', {
            'fields': ('contador_deteccoes', 'ultima_deteccao', 'estatisticas_display'),
            'classes': ('collapse',)
        }),
        ('Visual', {
            'fields': ('cor_identificacao', 'ordem_exibicao'),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('observacoes', 'criado_em', 'atualizado_em', 'criado_por'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)

    def esta_no_periodo_display(self, obj):
        if obj.esta_no_periodo:
            return format_html('<span style="color: green;">✓ Sim</span>')
        return format_html('<span style="color: red;">✗ Não</span>')
    esta_no_periodo_display.short_description = 'No Período'

    def total_leads_display(self, obj):
        total = obj.total_leads
        if total > 0:
            return format_html('<strong>{}</strong>', total)
        return total
    total_leads_display.short_description = 'Total Leads'

    def estatisticas_display(self, obj):
        html = f"""
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Total de Detecções:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{obj.contador_deteccoes}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Total de Leads:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{obj.total_leads}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Total de Conversões:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{obj.total_conversoes}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Taxa de Conversão:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{obj.taxa_conversao}%</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Receita Total:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">R$ {obj.receita_total}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>ROI:</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{f"{obj.roi}%" if obj.roi else "N/A"}</td>
            </tr>
        </table>
        """
        return format_html(html)
    estatisticas_display.short_description = 'Estatísticas da Campanha'


@admin.register(DeteccaoCampanha)
class DeteccaoCampanhaAdmin(admin.ModelAdmin):
    list_display = [
        'campanha', 'telefone', 'lead', 'score_confianca',
        'origem', 'aceita', 'converteu_venda', 'detectado_em'
    ]
    list_filter = [
        'aceita', 'converteu_venda', 'origem', 'metodo_deteccao',
        'processado_n8n', 'eh_primeira_mensagem', 'detectado_em'
    ]
    search_fields = ['telefone', 'mensagem_original', 'trecho_detectado']
    readonly_fields = [
        'lead', 'campanha', 'mensagem_normalizada', 'tamanho_mensagem',
        'detectado_em', 'data_processamento_n8n', 'data_conversao'
    ]

    fieldsets = (
        ('Relacionamentos', {
            'fields': ('lead', 'campanha')
        }),
        ('Mensagem', {
            'fields': (
                'telefone', 'mensagem_original', 'mensagem_normalizada',
                'tamanho_mensagem', 'timestamp_mensagem'
            )
        }),
        ('Detecção', {
            'fields': (
                'trecho_detectado', 'posicao_inicio', 'posicao_fim',
                'metodo_deteccao', 'score_confianca'
            )
        }),
        ('Contexto', {
            'fields': ('eh_primeira_mensagem', 'origem', 'ip_origem', 'user_agent', 'metadata')
        }),
        ('Validação', {
            'fields': ('aceita', 'motivo_rejeicao', 'rejeitada_por', 'data_rejeicao')
        }),
        ('N8N', {
            'fields': ('processado_n8n', 'data_processamento_n8n', 'resposta_n8n'),
            'classes': ('collapse',)
        }),
        ('Conversão', {
            'fields': ('converteu_venda', 'data_conversao', 'valor_venda')
        }),
        ('Auditoria', {
            'fields': ('detectado_em',),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.aceita and not obj.rejeitada_por:
            obj.rejeitada_por = request.user
            obj.data_rejeicao = timezone.now()
        super().save_model(request, obj, form, change)
