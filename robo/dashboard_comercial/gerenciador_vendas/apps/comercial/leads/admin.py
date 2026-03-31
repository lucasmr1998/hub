from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from apps.comercial.leads.models import (
    LeadProspecto,
    Prospecto,
    HistoricoContato,
    ImagemLeadProspecto,
)
from apps.comercial.atendimento.models import AtendimentoFluxo
from apps.comercial.cadastro.models import DocumentoLead


class ProspectoInline(admin.TabularInline):
    model = Prospecto
    fields = ('nome_prospecto', 'status', 'prioridade', 'data_criacao')
    readonly_fields = ('data_criacao',)
    extra = 0
    show_change_link = True


class HistoricoContatoInline(admin.TabularInline):
    model = HistoricoContato
    fields = ('telefone', 'status', 'sucesso', 'data_hora_contato')
    readonly_fields = ('data_hora_contato',)
    extra = 0
    show_change_link = True


class AtendimentoFluxoInline(admin.TabularInline):
    """Inline para atendimentos de fluxo dentro do lead"""
    model = AtendimentoFluxo
    fields = ('fluxo', 'status', 'questao_atual', 'questoes_respondidas', 'data_inicio')
    readonly_fields = ('data_inicio',)
    extra = 0
    show_change_link = True
    ordering = ['-data_inicio']
    verbose_name = "Atendimento de Fluxo"
    verbose_name_plural = "Atendimentos de Fluxo"


class DocumentoLeadInline(admin.TabularInline):
    """Inline para documentos do lead"""
    model = DocumentoLead
    fields = ('tipo_documento', 'status', 'nome_arquivo', 'formato_arquivo', 'data_upload', 'visualizar_documento')
    readonly_fields = ('nome_arquivo', 'formato_arquivo', 'data_upload', 'visualizar_documento')
    extra = 0
    show_change_link = True
    ordering = ['-data_upload']
    verbose_name = "Documento"
    verbose_name_plural = "Documentos"

    def visualizar_documento(self, obj):
        if obj.arquivo_base64:
            return format_html(
                '<a href="#" onclick="window.open(\'data:image/{};base64,{}\', \'_blank\'); return false;" style="color:#3498db;">Ver Imagem</a>',
                obj.formato_arquivo, obj.arquivo_base64
            )
        return "N/A"
    visualizar_documento.short_description = "Visualizar"


class ImagemLeadInline(admin.TabularInline):
    model = ImagemLeadProspecto
    fields = ('link_url', 'descricao', 'preview_imagem', 'data_criacao')
    readonly_fields = ('preview_imagem', 'data_criacao')
    extra = 1
    ordering = ['-data_criacao']
    verbose_name = "Imagem"
    verbose_name_plural = "Imagens"

    def preview_imagem(self, obj):
        if obj.link_url:
            return format_html(
                '<a href="{url}" target="_blank">'
                '<img src="{url}" style="max-height:80px;max-width:120px;border-radius:6px;border:1px solid #ddd;" />'
                '</a>',
                url=obj.link_url,
            )
        return "-"
    preview_imagem.short_description = "Preview"


@admin.register(LeadProspecto)
class LeadProspectoAdmin(admin.ModelAdmin):
    list_display = [
        'nome_razaosocial',
        'email',
        'telefone',
        'id_hubsoft',
        'origem_badge',
        'get_valor_formatado',
        'status_api_badge',
        'status_contrato_badge',
        'data_cadastro',
        'ativo_badge'
    ]
    list_filter = [
        'origem',
        'status_api',
        'ativo',
        'documentacao_validada',
        'anexos_contrato_enviados',
        'contrato_aceito',
        'data_cadastro',
        'data_nascimento',
        'estado',
        'bairro'
    ]
    search_fields = [
        'nome_razaosocial',
        'email',
        'telefone',
        'empresa',
        'cpf_cnpj',
        'id_hubsoft',
        'id_origem',
        'id_origem_servico',
        'rua',
        'bairro',
        'cidade',
        'cep',
        'ponto_referencia'
    ]
    readonly_fields = [
        'data_cadastro',
        'data_atualizacao',
        'get_valor_formatado',
        'url_pdf_conversa_link',
        'data_geracao_pdf',
        'html_conversa_link',
        'data_geracao_html',
        'anexos_contrato_enviados',
        'contrato_aceito',
        'data_aceite_contrato',
    ]
    fieldsets = (
        ('👤 Informações Principais', {
            'fields': (
                'nome_razaosocial',
                'email',
                'telefone',
                'empresa',
                'id_hubsoft',
                'id_origem',
                'id_origem_servico'
            ),
            'description': 'Dados básicos do lead/cliente'
        }),
        ('📄 Documentos e Localização', {
            'fields': (
                'cpf_cnpj',
                'rg',
                'endereco',
                'rua',
                'numero_residencia',
                'bairro',
                'cidade',
                'estado',
                'cep',
                'ponto_referencia'
            ),
            'classes': ('collapse',),
            'description': 'Informações de documentos e endereço'
        }),
        ('💼 Dados Comerciais', {
            'fields': (
                'id_plano_rp',
                'id_dia_vencimento',
                'id_vendedor_rp',
                'data_nascimento'
            ),
            'classes': ('collapse',),
            'description': 'Informações comerciais e de vendedor'
        }),
        ('💰 Vendas e Status', {
            'fields': (
                'valor',
                'origem',
                'status_api',
                'ativo'
            ),
            'description': 'Status do lead e informações de venda'
        }),
        ('📝 Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',),
            'description': 'Anotações e observações sobre o lead'
        }),
        ('📄 Documentação e Validação', {
            'fields': (
                'documentacao_completa',
                'documentacao_validada',
                'data_documentacao_completa',
                'data_documentacao_validada',
            ),
            'classes': ('collapse',),
        }),
        ('📑 PDF da Conversa', {
            'fields': (
                'url_pdf_conversa_link',
                'data_geracao_pdf',
            ),
            'description': (
                'A URL do PDF é gerada automaticamente quando todos os documentos forem validados. '
                'O código e protocolo são lidos do Histórico de Contato mais recente do lead.'
            ),
        }),
        ('💬 HTML da Conversa do Atendimento', {
            'fields': (
                'html_conversa_link',
                'data_geracao_html',
            ),
            'description': 'Conversa do atendimento gerada automaticamente ao validar os documentos.',
        }),
        ('📋 Contrato HubSoft', {
            'fields': (
                'anexos_contrato_enviados',
                'contrato_aceito',
                'data_aceite_contrato',
            ),
            'description': (
                'Acompanhamento do processo de anexação de documentos e aceite do contrato no HubSoft. '
                'O processo é executado automaticamente após a validação de todos os documentos.'
            ),
        }),
        ('🔧 Dados do Sistema', {
            'fields': (
                'data_cadastro',
                'data_atualizacao'
            ),
            'classes': ('collapse',),
            'description': 'Informações técnicas e de auditoria'
        })
    )
    date_hierarchy = 'data_cadastro'
    ordering = ['-data_cadastro']
    list_per_page = 25
    inlines = [ProspectoInline, HistoricoContatoInline, AtendimentoFluxoInline, DocumentoLeadInline, ImagemLeadInline]
    save_on_top = True
    actions = ['ativar_leads', 'inativar_leads', 'exportar_csv', 'reprocessar_anexos_contrato']

    def get_valor_formatado(self, obj):
        try:
            return obj.get_valor_formatado()
        except (TypeError, AttributeError):
            return "R$ 0,00"
    get_valor_formatado.short_description = 'Valor'
    get_valor_formatado.admin_order_field = 'valor'

    def status_api_badge(self, obj):
        colors = {
            'pendente': '#f39c12',
            'processado': '#3498db',
            'erro': '#e74c3c',
            'sucesso': '#2ecc71',
            'rejeitado': '#c0392b',
            'aguardando_retry': '#8e44ad',
            'processamento_manual': '#16a085',
        }
        color = colors.get(obj.status_api, '#7f8c8d')
        label = obj.get_status_api_display() if hasattr(obj, 'get_status_api_display') else obj.status_api
        return format_html('<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;font-size:11px;">{}</span>', color, label)
    status_api_badge.short_description = 'Status'
    status_api_badge.admin_order_field = 'status_api'

    def origem_badge(self, obj):
        colors = {
            'whatsapp': '#25D366',
            'instagram': '#C13584',
            'facebook': '#1877F2',
            'google': '#DB4437',
            'site': '#2c3e50',
            'indicacao': '#16a085',
            'telefone': '#2980b9',
            'email': '#8e44ad',
            'outros': '#7f8c8d',
        }
        color = colors.get(obj.origem, '#7f8c8d')
        label = obj.get_origem_display() if hasattr(obj, 'get_origem_display') else obj.origem
        return format_html('<span style="padding:2px 8px;border-radius:12px;border:1px solid {};color:{};font-size:11px;">{}</span>', color, color, label)
    origem_badge.short_description = 'Origem'
    origem_badge.admin_order_field = 'origem'

    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color:#2ecc71;font-weight:600;">Ativo</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">Inativo</span>')
    ativo_badge.short_description = 'Ativo'
    ativo_badge.admin_order_field = 'ativo'

    def url_pdf_conversa_link(self, obj):
        url = obj.url_pdf_conversa
        if url:
            return format_html(
                '<a href="{}" target="_blank" style="padding:4px 12px;background:#2ecc71;'
                'color:#fff;border-radius:6px;text-decoration:none;font-size:12px;">'
                '📄 Baixar PDF da Conversa</a>',
                url,
            )
        if obj.codigo_atendimento_pdf and obj.protocolo_atendimento_pdf:
            return format_html(
                '<span style="color:#f39c12;">⏳ Aguardando validação de todos os documentos</span>'
            )
        return format_html('<span style="color:#95a5a6;">Preencha código e protocolo acima</span>')
    url_pdf_conversa_link.short_description = 'PDF da Conversa'

    def html_conversa_link(self, obj):
        if obj.html_conversa_path:
            url_html = f"/leads/{obj.pk}/conversa/"
            url_pdf = f"/leads/{obj.pk}/conversa/pdf/"
            return format_html(
                '<a href="{}" target="_blank" style="padding:4px 12px;background:#25d366;'
                'color:#fff;border-radius:6px;text-decoration:none;font-size:12px;margin-right:8px;">'
                '💬 Abrir HTML</a>'
                '<a href="{}" target="_blank" style="padding:4px 12px;background:#e74c3c;'
                'color:#fff;border-radius:6px;text-decoration:none;font-size:12px;">'
                '📄 Abrir PDF</a>',
                url_html,
                url_pdf,
            )
        return format_html('<span style="color:#95a5a6;">Não gerado ainda</span>')
    html_conversa_link.short_description = 'Conversa HTML / PDF'

    def status_contrato_badge(self, obj):
        if obj.contrato_aceito:
            return format_html(
                '<span style="padding:2px 8px;border-radius:12px;background:#27ae60;'
                'color:#fff;font-size:11px;">✅ Aceito</span>'
            )
        if obj.anexos_contrato_enviados:
            return format_html(
                '<span style="padding:2px 8px;border-radius:12px;background:#3498db;'
                'color:#fff;font-size:11px;">📎 Anexado</span>'
            )
        if obj.documentacao_validada and obj.html_conversa_path:
            return format_html(
                '<span style="padding:2px 8px;border-radius:12px;background:#f39c12;'
                'color:#fff;font-size:11px;">⏳ Pendente</span>'
            )
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:#bdc3c7;'
            'color:#fff;font-size:11px;">— N/A</span>'
        )
    status_contrato_badge.short_description = 'Contrato'
    status_contrato_badge.admin_order_field = 'contrato_aceito'

    # Acoes em massa
    def ativar_leads(self, request, queryset):
        updated = queryset.update(ativo=True)
        self.message_user(request, f"{updated} lead(s) ativado(s).")
    ativar_leads.short_description = 'Ativar selecionados'

    def inativar_leads(self, request, queryset):
        updated = queryset.update(ativo=False)
        self.message_user(request, f"{updated} lead(s) inativado(s).")
    inativar_leads.short_description = 'Inativar selecionados'

    def exportar_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="leads_export.csv"'
        writer = csv.writer(response)
        headers = [
            'id', 'nome_razaosocial', 'email', 'telefone', 'empresa', 'origem',
            'status_api', 'valor', 'cep', 'cidade', 'estado', 'bairro', 'rua',
            'numero_residencia', 'id_hubsoft', 'id_plano_rp', 'id_dia_vencimento',
            'id_vendedor_rp', 'data_nascimento', 'data_cadastro', 'data_atualizacao', 'ativo'
        ]
        writer.writerow(headers)
        for obj in queryset:
            writer.writerow([
                obj.id, obj.nome_razaosocial, obj.email, obj.telefone, obj.empresa, obj.origem,
                obj.status_api, obj.valor, obj.cep, obj.cidade, obj.estado, getattr(obj, 'bairro', ''), getattr(obj, 'rua', ''),
                getattr(obj, 'numero_residencia', ''), obj.id_hubsoft, getattr(obj, 'id_plano_rp', ''), getattr(obj, 'id_dia_vencimento', ''),
                getattr(obj, 'id_vendedor_rp', ''), getattr(obj, 'data_nascimento', ''), obj.data_cadastro, obj.data_atualizacao, obj.ativo
            ])
        return response
    exportar_csv.short_description = 'Exportar selecionados como CSV'

    def reprocessar_anexos_contrato(self, request, queryset):
        from django.utils.html import format_html

        leads_aptos = queryset.filter(
            documentacao_validada=True,
            html_conversa_path__isnull=False,
        ).exclude(html_conversa_path='')

        if not leads_aptos.exists():
            self.message_user(
                request,
                "Nenhum lead selecionado possui documentação validada e HTML gerado.",
                level='warning',
            )
            return

        leads_aptos.update(anexos_contrato_enviados=False)

        sucesso = 0
        erro = 0
        for lead in leads_aptos:
            try:
                from vendas_web.services.contrato_service import anexar_documentos_e_aceitar_contrato
                resultado = anexar_documentos_e_aceitar_contrato(lead)
                if resultado:
                    sucesso += 1
                else:
                    erro += 1
            except Exception as exc:
                erro += 1
                import logging
                logging.getLogger(__name__).error(
                    "Erro ao reprocessar contrato do lead %s: %s", lead.pk, exc
                )

        msg = f"{sucesso} lead(s) processado(s) com sucesso."
        if erro:
            msg += f" {erro} lead(s) com erro (verifique os logs)."
            self.message_user(request, msg, level='warning')
        else:
            self.message_user(request, msg)

    reprocessar_anexos_contrato.short_description = '📎 Reprocessar anexos e aceite de contrato'


@admin.register(Prospecto)
class ProspectoAdmin(admin.ModelAdmin):
    list_display = [
        'nome_prospecto',
        'lead',
        'status',
        'tentativas_processamento',
        'get_tempo_processamento_formatado',
        'data_criacao',
        'data_processamento'
    ]
    list_filter = [
        'status',
        'prioridade',
        'data_criacao',
        'tentativas_processamento'
    ]
    search_fields = [
        'nome_prospecto',
        'id_prospecto_hubsoft',
        'lead__nome_razaosocial',
        'lead__email'
    ]
    readonly_fields = [
        'data_criacao',
        'get_tempo_processamento_formatado'
    ]
    fieldsets = (
        ('Informações do Prospecto', {
            'fields': (
                'nome_prospecto',
                'lead',
                'id_prospecto_hubsoft',
                'status',
                'prioridade'
            )
        }),
        ('Processamento', {
            'fields': (
                'data_processamento',
                'tentativas_processamento',
                'tempo_processamento',
                'erro_processamento'
            )
        }),
        ('Dados JSON', {
            'fields': (
                'dados_processamento',
                'resultado_processamento'
            ),
            'classes': ('collapse',)
        }),
        ('Dados do Sistema', {
            'fields': ('data_criacao',),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'data_criacao'
    ordering = ['-data_criacao']
    list_per_page = 25
    autocomplete_fields = ('lead',)
    list_select_related = ('lead',)
    save_on_top = True

    def get_tempo_processamento_formatado(self, obj):
        try:
            return obj.get_tempo_processamento_formatado()
        except (TypeError, AttributeError):
            return "N/A"
    get_tempo_processamento_formatado.short_description = 'Tempo Processamento'
    get_tempo_processamento_formatado.admin_order_field = 'tempo_processamento'


@admin.register(HistoricoContato)
class HistoricoContatoAdmin(admin.ModelAdmin):
    list_display = [
        'telefone',
        'nome_contato',
        'protocolo_atendimento',
        'codigo_atendimento',
        'numero_conta',
        'status',
        'get_duracao_formatada',
        'sucesso',
        'data_hora_contato',
        'lead'
    ]
    list_filter = [
        'status',
        'sucesso',
        'data_hora_contato'
    ]
    search_fields = [
        'telefone',
        'nome_contato',
        'protocolo_atendimento',
        'codigo_atendimento',
        'id_conta',
        'numero_conta',
        'lead__nome_razaosocial',
        'lead__email'
    ]
    readonly_fields = [
        'data_hora_contato',
        'get_duracao_formatada',
        'get_tempo_relativo'
    ]
    fieldsets = (
        ('Informações do Contato', {
            'fields': (
                'telefone',
                'nome_contato',
                'lead',
                'status',
                'sucesso',
                'protocolo_atendimento',
                'codigo_atendimento'
            )
        }),
        ('Dados da Conta', {
            'fields': (
                'id_conta',
                'numero_conta'
            ),
            'classes': ('collapse',)
        }),
        ('Detalhes da Chamada', {
            'fields': (
                'data_hora_contato',
                'duracao_segundos',
                'ultima_mensagem',
                'transcricao',
                'observacoes'
            )
        }),
        ('Dados Técnicos', {
            'fields': (
                'ip_origem',
                'user_agent',
                'dados_extras'
            ),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'data_hora_contato'
    ordering = ['-data_hora_contato']
    list_per_page = 25

    def get_duracao_formatada(self, obj):
        try:
            return obj.get_duracao_formatada()
        except (TypeError, AttributeError):
            return "N/A"
    get_duracao_formatada.short_description = 'Duração'
    get_duracao_formatada.admin_order_field = 'duracao_segundos'

    def get_tempo_relativo(self, obj):
        try:
            return obj.get_tempo_relativo()
        except (TypeError, AttributeError):
            return "N/A"
    get_tempo_relativo.short_description = 'Há quanto tempo'


@admin.register(ImagemLeadProspecto)
class ImagemLeadProspectoAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'lead',
        'descricao',
        'status_validacao_badge',
        'validado_por',
        'data_validacao',
        'link_imagem',
        'data_criacao',
    ]
    list_filter = [
        'status_validacao',
        'data_validacao',
        'data_criacao',
    ]
    search_fields = [
        'lead__nome_razaosocial',
        'lead__telefone',
        'descricao',
        'validado_por',
    ]
    readonly_fields = [
        'data_criacao',
        'data_validacao',
        'link_imagem',
    ]
    fieldsets = (
        ('🔗 Vínculo', {
            'fields': ('lead', 'link_url', 'descricao'),
        }),
        ('✅ Validação', {
            'fields': (
                'status_validacao',
                'observacao_validacao',
                'data_validacao',
                'validado_por',
            ),
        }),
        ('🕐 Auditoria', {
            'fields': ('data_criacao',),
            'classes': ('collapse',),
        }),
    )
    ordering = ['-data_criacao']
    list_per_page = 30
    list_select_related = ['lead']
    actions = ['aprovar_documentos', 'rejeitar_documentos']

    def status_validacao_badge(self, obj):
        colors = {
            ImagemLeadProspecto.STATUS_VALIDO:    ('#2ecc71', '✅ Válido'),
            ImagemLeadProspecto.STATUS_REJEITADO: ('#e74c3c', '❌ Rejeitado'),
            ImagemLeadProspecto.STATUS_PENDENTE:  ('#f39c12', '⏳ Pendente'),
        }
        color, label = colors.get(obj.status_validacao, ('#95a5a6', obj.status_validacao))
        return format_html(
            '<span style="padding:3px 10px;border-radius:12px;background:{};'
            'color:#fff;font-size:11px;font-weight:600;">{}</span>',
            color, label,
        )
    status_validacao_badge.short_description = 'Status'
    status_validacao_badge.admin_order_field = 'status_validacao'

    def link_imagem(self, obj):
        if obj.link_url:
            return format_html(
                '<a href="{}" target="_blank" style="color:#2980b9;">🔗 Visualizar</a>',
                obj.link_url,
            )
        return '-'
    link_imagem.short_description = 'Link'

    def save_model(self, request, obj, form, change):
        if obj.status_validacao != ImagemLeadProspecto.STATUS_PENDENTE and not obj.validado_por:
            obj.validado_por = request.user.get_full_name() or request.user.username
        if obj.status_validacao != ImagemLeadProspecto.STATUS_PENDENTE and not obj.data_validacao:
            obj.data_validacao = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description='✅ Aprovar documentos selecionados')
    def aprovar_documentos(self, request, queryset):
        now = timezone.now()
        usuario = request.user.get_full_name() or request.user.username
        updated = queryset.update(
            status_validacao=ImagemLeadProspecto.STATUS_VALIDO,
            data_validacao=now,
            validado_por=usuario,
        )
        for imagem in queryset:
            imagem.status_validacao = ImagemLeadProspecto.STATUS_VALIDO
            imagem.save()
        self.message_user(request, f'{updated} documento(s) aprovado(s).')

    @admin.action(description='❌ Rejeitar documentos selecionados')
    def rejeitar_documentos(self, request, queryset):
        now = timezone.now()
        usuario = request.user.get_full_name() or request.user.username
        updated = queryset.update(
            status_validacao=ImagemLeadProspecto.STATUS_REJEITADO,
            data_validacao=now,
            validado_por=usuario,
        )
        self.message_user(request, f'{updated} documento(s) rejeitado(s).')
