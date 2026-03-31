from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PipelineEstagio, EquipeVendas, PerfilVendedor, TagCRM,
    OportunidadeVenda, HistoricoPipelineEstagio,
    TarefaCRM, NotaInterna, MetaVendas,
    SegmentoCRM, MembroSegmento, AlertaRetencao, ConfiguracaoCRM,
)


@admin.register(PipelineEstagio)
class PipelineEstagioAdmin(admin.ModelAdmin):
    list_display = ['ordem', 'nome', 'tipo', 'cor_badge', 'sla_horas', 'probabilidade_padrao', 'is_final_ganho', 'is_final_perdido', 'ativo']
    list_display_links = ['nome']
    list_editable = ['ordem', 'ativo']
    list_filter = ['tipo', 'ativo', 'is_final_ganho', 'is_final_perdido']
    ordering = ['ordem']

    def cor_badge(self, obj):
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:4px;">{}</span>',
            obj.cor_hex, obj.cor_hex
        )
    cor_badge.short_description = 'Cor'


@admin.register(EquipeVendas)
class EquipeVendasAdmin(admin.ModelAdmin):
    list_display = ['nome', 'lider', 'ativo', 'data_criacao']
    list_filter = ['ativo']
    search_fields = ['nome']


@admin.register(PerfilVendedor)
class PerfilVendedorAdmin(admin.ModelAdmin):
    list_display = ['user', 'cargo', 'equipe', 'telefone_direto', 'whatsapp', 'id_vendedor_hubsoft', 'ativo']
    list_filter = ['cargo', 'equipe', 'ativo']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user']


@admin.register(TagCRM)
class TagCRMAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cor_badge']

    def cor_badge(self, obj):
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:4px;">{}</span>',
            obj.cor_hex, obj.nome
        )
    cor_badge.short_description = 'Tag'


class HistoricoPipelineInline(admin.TabularInline):
    model = HistoricoPipelineEstagio
    extra = 0
    readonly_fields = ['estagio_anterior', 'estagio_novo', 'movido_por', 'tempo_no_estagio_horas', 'data_transicao']
    can_delete = False


class TarefaCRMInline(admin.TabularInline):
    model = TarefaCRM
    extra = 0
    fields = ['tipo', 'titulo', 'status', 'prioridade', 'data_vencimento', 'responsavel']


class NotaInternaInline(admin.TabularInline):
    model = NotaInterna
    extra = 0
    fields = ['tipo', 'conteudo', 'autor', 'is_fixada', 'data_criacao']
    readonly_fields = ['data_criacao']


@admin.register(OportunidadeVenda)
class OportunidadeVendaAdmin(admin.ModelAdmin):
    list_display = [
        'lead_nome', 'estagio', 'responsavel', 'prioridade',
        'valor_estimado', 'probabilidade', 'dias_no_estagio_display',
        'sla_badge', 'data_fechamento_previsto', 'ativo'
    ]
    list_filter = ['estagio', 'prioridade', 'ativo', 'origem_crm', 'responsavel']
    search_fields = ['lead__nome_razaosocial', 'lead__telefone', 'titulo']
    raw_id_fields = ['lead', 'responsavel']
    filter_horizontal = ['tags']
    readonly_fields = ['data_criacao', 'data_atualizacao', 'data_entrada_estagio']
    inlines = [HistoricoPipelineInline, TarefaCRMInline, NotaInternaInline]

    fieldsets = [
        ('Identificação', {'fields': ['lead', 'titulo', 'estagio', 'responsavel', 'criado_por', 'tags']}),
        ('Comercial', {'fields': ['valor_estimado', 'probabilidade', 'prioridade', 'plano_interesse', 'data_fechamento_previsto']}),
        ('Resultado', {'fields': ['data_fechamento_real', 'motivo_perda', 'concorrente_perdido', 'contrato_hubsoft_id']}),
        ('CRM', {'fields': ['origem_crm', 'churn_risk_score', 'ativo']}),
        ('Datas', {'fields': ['data_entrada_estagio', 'data_criacao', 'data_atualizacao'], 'classes': ['collapse']}),
    ]

    def lead_nome(self, obj):
        return obj.lead.nome_razaosocial
    lead_nome.short_description = 'Lead'

    def dias_no_estagio_display(self, obj):
        dias = obj.dias_no_estagio
        cor = '#e74c3c' if obj.sla_vencido else ('#f39c12' if dias > 3 else '#27ae60')
        return format_html('<span style="color:{};">{} dias</span>', cor, dias)
    dias_no_estagio_display.short_description = 'Dias no Estágio'

    def sla_badge(self, obj):
        if obj.sla_vencido:
            return format_html('<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:4px;">⚠ SLA</span>')
        return format_html('<span style="color:#27ae60;">✓ OK</span>')
    sla_badge.short_description = 'SLA'


@admin.register(HistoricoPipelineEstagio)
class HistoricoPipelineEstagioAdmin(admin.ModelAdmin):
    list_display = ['oportunidade', 'estagio_anterior', 'estagio_novo', 'movido_por', 'tempo_no_estagio_horas', 'data_transicao']
    list_filter = ['estagio_novo', 'estagio_anterior']
    readonly_fields = ['data_transicao']
    search_fields = ['oportunidade__lead__nome_razaosocial']


@admin.register(TarefaCRM)
class TarefaCRMAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo', 'status', 'prioridade', 'responsavel', 'data_vencimento', 'data_conclusao']
    list_filter = ['tipo', 'status', 'prioridade', 'responsavel']
    search_fields = ['titulo', 'responsavel__username', 'lead__nome_razaosocial']
    raw_id_fields = ['lead', 'oportunidade', 'responsavel']
    readonly_fields = ['data_criacao', 'data_atualizacao']


@admin.register(NotaInterna)
class NotaInternaAdmin(admin.ModelAdmin):
    list_display = ['autor', 'tipo', 'conteudo_resumo', 'is_fixada', 'data_criacao']
    list_filter = ['tipo', 'is_fixada', 'autor']
    search_fields = ['conteudo', 'autor__username']
    raw_id_fields = ['lead', 'oportunidade', 'autor']

    def conteudo_resumo(self, obj):
        return obj.conteudo[:80] + '...' if len(obj.conteudo) > 80 else obj.conteudo
    conteudo_resumo.short_description = 'Conteúdo'


@admin.register(MetaVendas)
class MetaVendasAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'vendedor', 'equipe', 'periodo', 'data_inicio', 'data_fim',
                    'meta_vendas_quantidade', 'realizado_vendas_quantidade', 'percentual_display']
    list_filter = ['tipo', 'periodo', 'vendedor', 'equipe']
    readonly_fields = ['data_criacao']

    def percentual_display(self, obj):
        pct = obj.percentual_quantidade
        cor = '#27ae60' if pct >= 100 else ('#f39c12' if pct >= 70 else '#e74c3c')
        return format_html('<span style="color:{};">{}%</span>', cor, pct)
    percentual_display.short_description = '% Qtd.'


@admin.register(SegmentoCRM)
class SegmentoCRMAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo', 'total_leads', 'ativo', 'data_criacao']
    list_filter = ['tipo', 'ativo']
    search_fields = ['nome']


@admin.register(AlertaRetencao)
class AlertaRetencaoAdmin(admin.ModelAdmin):
    list_display = ['cliente_hubsoft', 'tipo_alerta', 'nivel_risco', 'score_churn', 'status', 'responsavel', 'data_detectado']
    list_filter = ['tipo_alerta', 'nivel_risco', 'status', 'responsavel']
    search_fields = ['cliente_hubsoft__nome_razaosocial']
    raw_id_fields = ['cliente_hubsoft', 'lead', 'oportunidade']


@admin.register(ConfiguracaoCRM)
class ConfiguracaoCRMAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ConfiguracaoCRM.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
