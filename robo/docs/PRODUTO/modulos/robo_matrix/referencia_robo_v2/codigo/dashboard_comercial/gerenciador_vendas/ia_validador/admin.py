from django.contrib import admin
from .models import RegraValidacao


@admin.register(RegraValidacao)
class RegraValidacaoAdmin(admin.ModelAdmin):
    list_display = (
        'ordem', 'question_id', 'extractor_tipo', 'campo_lead_atualizar',
        'tags_resumo', 'status_api_apos_sucesso', 'ativo',
    )
    list_display_links = ('question_id',)
    list_filter = ('extractor_tipo', 'ativo', 'forcar_transbordo_apos_max')
    list_editable = ('ordem', 'ativo')
    search_fields = ('question_id', 'pergunta_padrao', 'descricao')
    ordering = ('ordem', 'question_id')

    fieldsets = (
        ('Identificação', {
            'fields': ('question_id', 'pergunta_padrao', 'ordem', 'descricao', 'ativo'),
        }),
        ('Validação', {
            'fields': ('extractor_tipo', 'extractor_config', 'instrucoes_ia',
                       'permite_pular', 'max_tentativas'),
        }),
        ('Ações ao validar com sucesso', {
            'fields': (
                'campo_lead_atualizar',
                'status_api_apos_sucesso',
                'tags_adicionar', 'tags_remover',
                'historico_status_apos_sucesso', 'historico_observacoes_template',
                'descricao_imagem',
            ),
        }),
        ('Mensagens ao cliente', {
            'fields': ('msg_sucesso', 'msg_erro', 'msg_max_tentativas',
                       'forcar_transbordo_apos_max'),
        }),
        ('Auditoria', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('data_criacao', 'data_atualizacao')

    def tags_resumo(self, obj):
        adds = obj.tags_adicionar or []
        return ', '.join(adds) if adds else '—'
    tags_resumo.short_description = 'Tags'
