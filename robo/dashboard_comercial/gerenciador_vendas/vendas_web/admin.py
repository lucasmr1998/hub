from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils import timezone
from django.db import models
from django import forms
from .models import (
    LeadProspecto, 
    Prospecto, 
    HistoricoContato, 
    ConfiguracaoSistema, 
    LogSistema,
    StatusConfiguravel,
    FluxoAtendimento,
    QuestaoFluxo,
    AtendimentoFluxo,
    RespostaQuestao,
    TentativaResposta,
    ConfiguracaoCadastro,
    PlanoInternet,
    OpcaoVencimento,
    CadastroCliente,
    DocumentoLead,
    ImagemLeadProspecto,
    ConfiguracaoEmpresa,
    # Modelos de Notificações
    TipoNotificacao,
    CanalNotificacao,
    PreferenciaNotificacao,
    Notificacao,
    # Modelos de Campanhas
    CampanhaTrafego,
    DeteccaoCampanha,
    TemplateNotificacao,
    # Viabilidade
    CidadeViabilidade,
)


class AdminSiteCustom(admin.AdminSite):
    site_header = 'Megalink - Painel Comercial'
    site_title = 'Megalink'
    index_title = 'Painel de Controle'
    
    def index(self, request, extra_context=None):
        """
        Página principal personalizada do admin
        """
        extra_context = extra_context or {}
        
        # Estatísticas rápidas
        try:
            from .models import LeadProspecto, Prospecto, AtendimentoFluxo, ConfiguracaoEmpresa, CadastroCliente, DocumentoLead
            
            total_leads = LeadProspecto.objects.count()
            leads_ativos = LeadProspecto.objects.filter(ativo=True).count()
            total_prospectos = Prospecto.objects.count()
            atendimentos_hoje = AtendimentoFluxo.objects.filter(
                data_inicio__date=timezone.now().date()
            ).count()
            
            # Estatísticas adicionais
            cadastros_mes = CadastroCliente.objects.filter(
                data_inicio__month=timezone.now().month,
                data_inicio__year=timezone.now().year
            ).count()
            
            documentos_pendentes = DocumentoLead.objects.filter(status='pendente').count()
            
            config_empresa = ConfiguracaoEmpresa.get_configuracao_ativa()
            
            extra_context.update({
                'estatisticas': {
                    'total_leads': total_leads,
                    'leads_ativos': leads_ativos,
                    'total_prospectos': total_prospectos,
                    'atendimentos_hoje': atendimentos_hoje,
                    'cadastros_mes': cadastros_mes,
                    'documentos_pendentes': documentos_pendentes,
                },
                'empresa_config': config_empresa,
            })
        except Exception as e:
            # Log do erro para debug
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao carregar estatísticas do admin: {e}")
        
        return super().index(request, extra_context)


# Criar instância customizada do admin
admin_site = AdminSiteCustom(name='admin')

# Configurar o site padrão também
admin.site.site_header = AdminSiteCustom.site_header
admin.site.site_title = AdminSiteCustom.site_title
admin.site.index_title = AdminSiteCustom.index_title


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

    # Ações em massa
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

        # Filtra apenas leads que têm documentação validada e HTML gerado
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

        # Reseta o flag para forçar reprocessamento
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


@admin.register(ConfiguracaoSistema)
class ConfiguracaoSistemaAdmin(admin.ModelAdmin):
    list_display = [
        'chave', 
        'valor_truncado', 
        'tipo', 
        'ativo', 
        'data_atualizacao'
    ]
    list_filter = [
        'tipo', 
        'ativo', 
        'data_criacao'
    ]
    search_fields = [
        'chave', 
        'valor', 
        'descricao'
    ]
    readonly_fields = [
        'data_criacao', 
        'data_atualizacao'
    ]
    fieldsets = (
        ('Configuração', {
            'fields': (
                'chave', 
                'valor', 
                'tipo', 
                'ativo'
            )
        }),
        ('Descrição', {
            'fields': ('descricao',)
        }),
        ('Dados do Sistema', {
            'fields': (
                'data_criacao', 
                'data_atualizacao'
            ),
            'classes': ('collapse',)
        })
    )
    ordering = ['chave']
    list_per_page = 25
    
    def valor_truncado(self, obj):
        if len(obj.valor) > 50:
            return f"{obj.valor[:50]}..."
        return obj.valor
    valor_truncado.short_description = 'Valor'


@admin.register(LogSistema)
class LogSistemaAdmin(admin.ModelAdmin):
    list_display = [
        'nivel', 
        'modulo', 
        'mensagem_truncada', 
        'usuario', 
        'ip', 
        'data_criacao'
    ]
    list_filter = [
        'nivel', 
        'modulo', 
        'data_criacao'
    ]
    search_fields = [
        'modulo', 
        'mensagem', 
        'usuario'
    ]
    readonly_fields = [
        'data_criacao'
    ]
    fieldsets = (
        ('Log', {
            'fields': (
                'nivel', 
                'modulo', 
                'mensagem'
            )
        }),
        ('Usuário e IP', {
            'fields': (
                'usuario', 
                'ip'
            )
        }),
        ('Dados Extras', {
            'fields': ('dados_extras',),
            'classes': ('collapse',)
        }),
        ('Data', {
            'fields': ('data_criacao',),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'data_criacao'
    ordering = ['-data_criacao']
    list_per_page = 25
    
    def mensagem_truncada(self, obj):
        if len(obj.mensagem) > 80:
            return f"{obj.mensagem[:80]}..."
        return obj.mensagem
    mensagem_truncada.short_description = 'Mensagem'
    
    def get_readonly_fields(self, request, obj=None):
        # Torna todos os campos readonly para logs (apenas visualização)
        if obj:
            return [field.name for field in obj._meta.fields]
        return self.readonly_fields


@admin.register(StatusConfiguravel)
class StatusConfiguravelAdmin(admin.ModelAdmin):
    list_display = ['grupo', 'codigo', 'rotulo', 'ativo', 'ordem']
    list_filter = ['grupo', 'ativo']
    search_fields = ['codigo', 'rotulo']
    list_editable = ['rotulo', 'ativo', 'ordem']
    ordering = ['grupo', 'ordem', 'codigo']


# ============================================================================
# ADMIN PARA FLUXOS DE ATENDIMENTO
# ============================================================================

class QuestaoFluxoInline(admin.TabularInline):
    """Inline para questões dentro do fluxo"""
    model = QuestaoFluxo
    fields = ('indice', 'titulo', 'tipo_questao', 'tipo_validacao', 'ativo')
    extra = 1
    show_change_link = True
    ordering = ['indice']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('questao_dependencia')
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        
        # Definir valores padrão para novos registros
        if obj:
            # Calcular próximo índice disponível
            ultimo_indice = obj.questoes.aggregate(
                models.Max('indice')
            )['indice__max'] or 0
            
            # Verificar se o campo indice existe antes de tentar acessá-lo
            if 'indice' in formset.form.base_fields:
                formset.form.base_fields['indice'].initial = ultimo_indice + 1
            if 'fluxo' in formset.form.base_fields:
                formset.form.base_fields['fluxo'].initial = obj
                formset.form.base_fields['fluxo'].widget = forms.HiddenInput()
        
        return formset
    
    def save_new_instance(self, request, instance, form, commit=True):
        # Garantir que o índice seja preenchido automaticamente
        if not instance.indice and instance.fluxo:
            ultimo_indice = instance.fluxo.questoes.aggregate(
                models.Max('indice')
            )['indice__max'] or 0
            instance.indice = ultimo_indice + 1
        
        return super().save_new_instance(request, instance, form, commit)


class AtendimentoFluxoInline(admin.TabularInline):
    """Inline para atendimentos dentro do fluxo"""
    model = AtendimentoFluxo
    fields = ('lead', 'status', 'questao_atual', 'questoes_respondidas', 'data_inicio')
    readonly_fields = ('data_inicio',)
    extra = 0
    show_change_link = True
    ordering = ['-data_inicio']


@admin.register(FluxoAtendimento)
class FluxoAtendimentoAdmin(admin.ModelAdmin):
    list_display = [
        'nome',
        'tipo_fluxo_badge',
        'status_badge',
        'get_total_questoes',
        'get_total_atendimentos',
        'get_taxa_completacao',
        'data_criacao',
        'ativo_badge'
    ]
    list_filter = [
        'tipo_fluxo',
        'status',
        'ativo',
        'data_criacao',
        'criado_por'
    ]
    search_fields = [
        'nome',
        'descricao',
        'criado_por'
    ]
    readonly_fields = [
        'data_criacao',
        'data_atualizacao',
        'get_total_questoes',
        'get_total_atendimentos',
        'get_estatisticas_formatadas'
    ]
    fieldsets = (
        ('🔄 Informações do Fluxo', {
            'fields': (
                'nome',
                'descricao',
                'tipo_fluxo',
                'status',
                'ativo'
            ),
            'description': 'Configure as informações básicas do fluxo de atendimento'
        }),
        ('⚙️ Configurações Avançadas', {
            'fields': (
                'max_tentativas',
                'tempo_limite_minutos',
                'permite_pular_questoes'
            ),
            'description': 'Defina comportamentos e limites do fluxo'
        }),
        ('👨‍💻 Controle e Auditoria', {
            'fields': (
                'criado_por',
                'data_criacao',
                'data_atualizacao'
            ),
            'classes': ('collapse',),
            'description': 'Informações de criação e modificação'
        }),
        ('📊 Estatísticas e Performance', {
            'fields': ('get_estatisticas_formatadas',),
            'classes': ('collapse',),
            'description': 'Métricas e estatísticas do fluxo'
        })
    )
    date_hierarchy = 'data_criacao'
    ordering = ['-data_criacao']
    list_per_page = 25
    inlines = [QuestaoFluxoInline, AtendimentoFluxoInline]
    save_on_top = True
    actions = ['ativar_fluxos', 'inativar_fluxos', 'duplicar_fluxos']
    
    def tipo_fluxo_badge(self, obj):
        colors = {
            'qualificacao': '#3498db',
            'vendas': '#2ecc71',
            'suporte': '#f39c12',
            'onboarding': '#9b59b6',
            'pesquisa': '#e67e22',
            'customizado': '#34495e',
        }
        color = colors.get(obj.tipo_fluxo, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;font-size:11px;">{}</span>',
            color, obj.get_tipo_fluxo_display()
        )
    tipo_fluxo_badge.short_description = 'Tipo'
    tipo_fluxo_badge.admin_order_field = 'tipo_fluxo'
    
    def status_badge(self, obj):
        colors = {
            'ativo': '#2ecc71',
            'inativo': '#e74c3c',
            'rascunho': '#95a5a6',
            'teste': '#f39c12',
        }
        color = colors.get(obj.status, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color:#2ecc71;font-weight:600;">✓ Ativo</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">✗ Inativo</span>')
    ativo_badge.short_description = 'Ativo'
    ativo_badge.admin_order_field = 'ativo'
    
    def get_total_questoes(self, obj):
        try:
            return obj.get_total_questoes()
        except (TypeError, AttributeError):
            return 0
    get_total_questoes.short_description = 'Questões'
    get_total_questoes.admin_order_field = 'questoes__count'
    
    def get_total_atendimentos(self, obj):
        try:
            return obj.atendimentos.count()
        except (TypeError, AttributeError):
            return 0
    get_total_atendimentos.short_description = 'Atendimentos'
    
    def get_taxa_completacao(self, obj):
        try:
            estatisticas = obj.get_estatisticas()
            return f"{estatisticas['taxa_completacao']}%"
        except (TypeError, AttributeError):
            return "0%"
    get_taxa_completacao.short_description = 'Taxa Completação'
    
    def get_estatisticas_formatadas(self, obj):
        if not obj.pk:
            return "Salve o fluxo para ver estatísticas"
        
        try:
            estatisticas = obj.get_estatisticas()
            total_questoes = obj.get_total_questoes()
        except (TypeError, AttributeError):
            return "Erro ao carregar estatísticas"
        
        # Link para adicionar nova questão
        add_questao_url = f"/admin/vendas_web/questaofluxo/add/?fluxo={obj.id}"
        
        html = f"""
        <div style="background:#f8f9fa;padding:15px;border-radius:8px;border:1px solid #dee2e6;">
            <h4 style="margin-top:0;color:#495057;">📊 Estatísticas do Fluxo</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                <div>
                    <strong>Total de Atendimentos:</strong> {estatisticas['total_atendimentos']}<br>
                    <strong>Completados:</strong> {estatisticas['atendimentos_completados']}<br>
                    <strong>Taxa de Completação:</strong> {estatisticas['taxa_completacao']}%
                </div>
                <div>
                    <strong>Tempo Médio:</strong> {estatisticas['tempo_medio_segundos']}s<br>
                    <strong>Questões Ativas:</strong> {total_questoes}<br>
                    <strong>Status:</strong> {obj.get_status_display()}
                </div>
            </div>
            <div style="margin-top:15px;text-align:center;">
                <a href="{add_questao_url}" class="button" style="background:#007cba;color:#fff;padding:8px 16px;text-decoration:none;border-radius:4px;">
                    ➕ Adicionar Nova Questão
                </a>
            </div>
        </div>
        """
        return format_html(html)
    get_estatisticas_formatadas.short_description = 'Estatísticas'
    
    # Ações em massa
    def ativar_fluxos(self, request, queryset):
        updated = queryset.update(ativo=True, status='ativo')
        self.message_user(request, f"{updated} fluxo(s) ativado(s).")
    ativar_fluxos.short_description = 'Ativar selecionados'
    
    def inativar_fluxos(self, request, queryset):
        updated = queryset.update(ativo=False, status='inativo')
        self.message_user(request, f"{updated} fluxo(s) inativado(s).")
    inativar_fluxos.short_description = 'Inativar selecionados'
    
    def duplicar_fluxos(self, request, queryset):
        for fluxo in queryset:
            # Duplicar fluxo
            novo_fluxo = FluxoAtendimento.objects.create(
                nome=f"{fluxo.nome} (Cópia)",
                descricao=f"Cópia de: {fluxo.descricao}",
                tipo_fluxo=fluxo.tipo_fluxo,
                status='rascunho',
                max_tentativas=fluxo.max_tentativas,
                tempo_limite_minutos=fluxo.tempo_limite_minutos,
                permite_pular_questoes=fluxo.permite_pular_questoes,
                criado_por=request.user.username if request.user.is_authenticated else 'admin'
            )
            
            # Duplicar questões
            for questao in fluxo.questoes.all():
                QuestaoFluxo.objects.create(
                    fluxo=novo_fluxo,
                    indice=questao.indice,
                    titulo=questao.titulo,
                    descricao=questao.descricao,
                    tipo_questao=questao.tipo_questao,
                    tipo_validacao=questao.tipo_validacao,
                    opcoes_resposta=questao.opcoes_resposta,
                    resposta_padrao=questao.resposta_padrao,
                    regex_validacao=questao.regex_validacao,
                    tamanho_minimo=questao.tamanho_minimo,
                    tamanho_maximo=questao.tamanho_maximo,
                    valor_minimo=questao.valor_minimo,
                    valor_maximo=questao.valor_maximo,
                    permite_voltar=questao.permite_voltar,
                    permite_editar=questao.permite_editar,
                    ordem_exibicao=questao.ordem_exibicao,
                    ativo=questao.ativo
                )
        
        self.message_user(request, f"{queryset.count()} fluxo(s) duplicado(s).")
    duplicar_fluxos.short_description = 'Duplicar selecionados'


class RespostaQuestaoInline(admin.TabularInline):
    """Inline para respostas dentro da questão"""
    model = RespostaQuestao
    fields = ('atendimento', 'resposta', 'valida', 'data_resposta')
    readonly_fields = ('data_resposta',)
    extra = 0
    show_change_link = True
    ordering = ['-data_resposta']


class TentativaRespostaInlineQuestao(admin.TabularInline):
    """Inline para tentativas de resposta dentro da questão"""
    model = TentativaResposta
    fields = ('atendimento', 'tentativa_numero', 'valida', 'confianca_ia', 'estrategia_aplicada', 'data_tentativa')
    readonly_fields = ('data_tentativa',)
    extra = 0
    show_change_link = True
    ordering = ['-data_tentativa']
    verbose_name = "Tentativa"
    verbose_name_plural = "Tentativas"


@admin.register(QuestaoFluxo)
class QuestaoFluxoAdmin(admin.ModelAdmin):
    list_display = [
        'fluxo',
        'indice',
        'titulo',
        'tipo_questao_badge',
        'tipo_validacao_badge',
        'opcoes_dinamicas_fonte_badge',
        'max_tentativas',
        'estrategia_erro_badge',
        'ativo_badge'
    ]
    list_filter = [
        'fluxo',
        'tipo_questao',
        'tipo_validacao',
        'opcoes_dinamicas_fonte',
        'estrategia_erro',
        'ativo',
        'permite_voltar',
        'permite_editar'
    ]
    search_fields = [
        'titulo',
        'descricao',
        'fluxo__nome'
    ]
    readonly_fields = [
        'get_opcoes_formatadas_display',
        'get_validacoes_display',
        'get_roteamento_display',
        'get_ia_config_display'
    ]
    fieldsets = (
        ('Questão Básica', {
            'fields': (
                'fluxo',
                'indice',
                'titulo',
                'descricao',
                'tipo_questao',
                'tipo_validacao',
                'ativo'
            )
        }),
        ('Opções Dinâmicas', {
            'fields': (
                'opcoes_dinamicas_fonte',
                'query_opcoes_dinamicas',
                'opcoes_resposta',
                'resposta_padrao',
                'get_opcoes_formatadas_display'
            ),
            'description': 'Configure opções que vêm do banco de dados (planos, vencimentos, etc.)'
        }),
        ('Roteamento Inteligente', {
            'fields': (
                'roteamento_respostas',
                'questao_padrao_proxima',
                'get_roteamento_display'
            ),
            'description': 'Configure para onde o usuário vai baseado na resposta'
        }),
        ('Validação por IA', {
            'fields': (
                'prompt_ia_validacao',
                'criterios_ia',
                'webhook_n8n_validacao',
                'get_ia_config_display'
            ),
            'classes': ('collapse',),
            'description': 'Configurações para validação inteligente'
        }),
        ('Controle de Erros', {
            'fields': (
                'max_tentativas',
                'estrategia_erro',
                'questao_erro_redirecionamento',
                'mensagem_erro_padrao',
                'mensagem_tentativa_esgotada',
                'instrucoes_resposta_correta'
            ),
            'description': 'Como lidar com respostas inválidas'
        }),
        ('Validações Tradicionais', {
            'fields': (
                'regex_validacao',
                'tamanho_minimo',
                'tamanho_maximo',
                'valor_minimo',
                'valor_maximo',
                'get_validacoes_display'
            ),
            'classes': ('collapse',)
        }),
        ('Webhooks N8N', {
            'fields': (
                'webhook_n8n_pos_resposta',
            ),
            'classes': ('collapse',),
            'description': 'Ações após resposta válida'
        }),
        ('Contexto e Template', {
            'fields': (
                'variaveis_contexto',
                'template_questao'
            ),
            'classes': ('collapse',)
        }),
        ('Dependências (Legado)', {
            'fields': (
                'questao_dependencia',
                'valor_dependencia'
            ),
            'classes': ('collapse',)
        }),
        ('Controle de Navegação', {
            'fields': (
                'permite_voltar',
                'permite_editar',
                'ordem_exibicao'
            )
        })
    )
    ordering = ['fluxo', 'indice']
    list_per_page = 25
    inlines = [RespostaQuestaoInline, TentativaRespostaInlineQuestao]
    save_on_top = True
    autocomplete_fields = ['fluxo', 'questao_dependencia']
    list_select_related = ['fluxo']
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Se é um novo registro, preencher índice automaticamente
        if not obj:
            # Tentar obter o fluxo do parâmetro GET
            fluxo_id = request.GET.get('fluxo')
            if fluxo_id:
                try:
                    fluxo = FluxoAtendimento.objects.get(id=fluxo_id)
                    ultimo_indice = fluxo.questoes.aggregate(
                        models.Max('indice')
                    )['indice__max'] or 0
                    form.base_fields['indice'].initial = ultimo_indice + 1
                    form.base_fields['fluxo'].initial = fluxo
                except FluxoAtendimento.DoesNotExist:
                    pass
        
        return form
    
    def save_model(self, request, obj, form, change):
        # Se é um novo registro e não tem índice, calcular automaticamente
        if not change and not obj.indice:
            if obj.fluxo:
                ultimo_indice = obj.fluxo.questoes.aggregate(
                    models.Max('indice')
                )['indice__max'] or 0
                obj.indice = ultimo_indice + 1
        
        super().save_model(request, obj, form, change)
    
    def tipo_questao_badge(self, obj):
        colors = {
            'texto': '#3498db',
            'numero': '#2ecc71',
            'email': '#9b59b6',
            'telefone': '#f39c12',
            'cpf_cnpj': '#e67e22',
            'cep': '#34495e',
            'endereco': '#16a085',
            'select': '#8e44ad',
            'multiselect': '#d35400',
            'data': '#27ae60',
            'hora': '#2980b9',
            'data_hora': '#c0392b',
            'boolean': '#e74c3c',
            'escala': '#f1c40f',
            'arquivo': '#95a5a6',
        }
        color = colors.get(obj.tipo_questao, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;background:{};color:#fff;font-size:10px;">{}</span>',
            color, obj.get_tipo_questao_display()
        )
    tipo_questao_badge.short_description = 'Tipo'
    tipo_questao_badge.admin_order_field = 'tipo_questao'
    
    def tipo_validacao_badge(self, obj):
        colors = {
            'obrigatoria': '#e74c3c',
            'opcional': '#95a5a6',
            'condicional': '#f39c12',
        }
        color = colors.get(obj.tipo_validacao, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;background:{};color:#fff;font-size:10px;">{}</span>',
            color, obj.get_tipo_validacao_display()
        )
    tipo_validacao_badge.short_description = 'Validação'
    tipo_validacao_badge.admin_order_field = 'tipo_validacao'
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color:#2ecc71;font-weight:600;">✓</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">✗</span>')
    ativo_badge.short_description = 'Ativa'
    ativo_badge.admin_order_field = 'ativo'
    
    def get_opcoes_formatadas_display(self, obj):
        if obj.opcoes_resposta:
            try:
                opcoes = obj.get_opcoes_formatadas()
                if opcoes:
                    html = '<div style="background:#f8f9fa;padding:8px;border-radius:4px;border:1px solid #dee2e6;">'
                    html += '<strong>Opções disponíveis:</strong><br>'
                    for i, opcao in enumerate(opcoes, 1):
                        html += f"{i}. {opcao}<br>"
                    html += '</div>'
                    return format_html(html)
            except (TypeError, AttributeError):
                return "Erro ao carregar opções"
        return "Nenhuma opção definida"
    get_opcoes_formatadas_display.short_description = 'Opções de Resposta'
    
    def get_validacoes_display(self, obj):
        try:
            validacoes = []
            if obj.regex_validacao:
                validacoes.append(f"Regex: {obj.regex_validacao}")
            if obj.tamanho_minimo:
                validacoes.append(f"Min: {obj.tamanho_minimo} chars")
            if obj.tamanho_maximo:
                validacoes.append(f"Max: {obj.tamanho_maximo} chars")
            if obj.valor_minimo is not None:
                validacoes.append(f"Valor min: {obj.valor_minimo}")
            if obj.valor_maximo is not None:
                validacoes.append(f"Valor max: {obj.valor_maximo}")
            
            if validacoes:
                html = '<div style="background:#f8f9fa;padding:8px;border-radius:4px;border:1px solid #dee2e6;">'
                html += '<strong>Validações ativas:</strong><br>'
                for validacao in validacoes:
                    html += f"• {validacao}<br>"
                html += '</div>'
                return format_html(html)
            return "Nenhuma validação específica"
        except (TypeError, AttributeError):
            return "Erro ao carregar validações"
    get_validacoes_display.short_description = 'Validações'
    
    def opcoes_dinamicas_fonte_badge(self, obj):
        if obj.opcoes_dinamicas_fonte:
            colors = {
                'planos_internet': '#3498db',
                'opcoes_vencimento': '#2ecc71',
                'customizada': '#f39c12',
            }
            color = colors.get(obj.opcoes_dinamicas_fonte, '#7f8c8d')
            return format_html(
                '<span style="padding:2px 6px;border-radius:8px;background:{};color:#fff;font-size:10px;">{}</span>',
                color, obj.get_opcoes_dinamicas_fonte_display()
            )
        return "—"
    opcoes_dinamicas_fonte_badge.short_description = 'Fonte Dinâmica'
    opcoes_dinamicas_fonte_badge.admin_order_field = 'opcoes_dinamicas_fonte'
    
    def estrategia_erro_badge(self, obj):
        colors = {
            'repetir': '#f39c12',
            'pular': '#3498db',
            'redirecionar': '#9b59b6',
            'finalizar': '#e74c3c',
            'escalar_humano': '#e67e22',
        }
        color = colors.get(obj.estrategia_erro, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;background:{};color:#fff;font-size:10px;">{}</span>',
            color, obj.get_estrategia_erro_display()
        )
    estrategia_erro_badge.short_description = 'Estratégia Erro'
    estrategia_erro_badge.admin_order_field = 'estrategia_erro'
    
    def get_roteamento_display(self, obj):
        if obj.roteamento_respostas:
            try:
                html = '<div style="background:#f8f9fa;padding:8px;border-radius:4px;border:1px solid #dee2e6;">'
                html += '<strong>Roteamento configurado:</strong><br>'
                for resposta, questao_id in obj.roteamento_respostas.items():
                    html += f"• '{resposta}' → Q{questao_id}<br>"
                html += '</div>'
                return format_html(html)
            except (TypeError, AttributeError):
                return "Erro ao carregar roteamento"
        return "Nenhum roteamento específico"
    get_roteamento_display.short_description = 'Roteamento'
    
    def get_ia_config_display(self, obj):
        configs = []
        if obj.prompt_ia_validacao:
            configs.append("Prompt IA configurado")
        if obj.criterios_ia:
            configs.append("Critérios IA definidos")
        if obj.webhook_n8n_validacao:
            configs.append("Webhook N8N ativo")
            
        if configs:
            html = '<div style="background:#e8f5e8;padding:8px;border-radius:4px;border:1px solid #c3e6c3;">'
            html += '<strong>Configurações IA:</strong><br>'
            for config in configs:
                html += f"✓ {config}<br>"
            html += '</div>'
            return format_html(html)
        return "Nenhuma configuração IA"
    get_ia_config_display.short_description = 'Configuração IA'


class RespostaQuestaoInlineAtendimento(admin.TabularInline):
    """Inline para respostas dentro do atendimento"""
    model = RespostaQuestao
    fields = ('questao', 'resposta', 'valida', 'tentativas', 'data_resposta')
    readonly_fields = ('data_resposta',)
    extra = 0
    show_change_link = True
    ordering = ['questao__indice']


class TentativaRespostaInlineAtendimento(admin.TabularInline):
    """Inline para tentativas de resposta dentro do atendimento"""
    model = TentativaResposta
    fields = ('questao', 'tentativa_numero', 'valida', 'confianca_ia', 'estrategia_aplicada', 'data_tentativa')
    readonly_fields = ('data_tentativa',)
    extra = 0
    show_change_link = True
    ordering = ['-data_tentativa']
    verbose_name = "Tentativa de Resposta"
    verbose_name_plural = "Tentativas de Resposta"


@admin.register(AtendimentoFluxo)
class AtendimentoFluxoAdmin(admin.ModelAdmin):
    list_display = [
        'lead',
        'fluxo',
        'status_badge',
        'questao_atual',
        'get_progresso_display',
        'get_tempo_formatado',
        'score_qualificacao',
        'data_inicio'
    ]
    list_filter = [
        'status',
        'fluxo',
        'fluxo__tipo_fluxo',
        'data_inicio',
        'data_conclusao',
        'score_qualificacao'
    ]
    search_fields = [
        'lead__nome_razaosocial',
        'lead__email',
        'lead__telefone',
        'fluxo__nome',
        'id_externo'
    ]
    readonly_fields = [
        'data_inicio',
        'data_ultima_atividade',
        'data_conclusao',
        'get_progresso_display',
        'get_tempo_formatado',
        'get_respostas_formatadas_display',
        'get_estatisticas_display',
        'get_estatisticas_tentativas_display'
    ]
    fieldsets = (
        ('Atendimento', {
            'fields': (
                'lead',
                'fluxo',
                'status',
                'id_externo'
            )
        }),
        ('Progresso', {
            'fields': (
                'questao_atual',
                'total_questoes',
                'questoes_respondidas',
                'get_progresso_display'
            )
        }),
        ('Tempo', {
            'fields': (
                'data_inicio',
                'data_ultima_atividade',
                'data_conclusao',
                'get_tempo_formatado'
            )
        }),
        ('Controle', {
            'fields': (
                'tentativas_atual',
                'max_tentativas',
                'score_qualificacao'
            )
        }),
        ('Dados', {
            'fields': (
                'dados_respostas',
                'observacoes',
                'resultado_final'
            ),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': (
                'ip_origem',
                'user_agent',
                'dispositivo'
            ),
            'classes': ('collapse',)
        }),
        ('Respostas', {
            'fields': ('get_respostas_formatadas_display',),
            'classes': ('collapse',)
        }),
        ('Estatísticas', {
            'fields': ('get_estatisticas_display',),
            'classes': ('collapse',)
        }),
        ('Tentativas Inteligentes', {
            'fields': ('get_estatisticas_tentativas_display',),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'data_inicio'
    ordering = ['-data_inicio']
    list_per_page = 25
    inlines = [RespostaQuestaoInlineAtendimento, TentativaRespostaInlineAtendimento]
    save_on_top = True
    autocomplete_fields = ['lead', 'fluxo', 'historico_contato']
    list_select_related = ['lead', 'fluxo']
    actions = ['reiniciar_atendimentos', 'finalizar_atendimentos', 'calcular_scores']
    
    def status_badge(self, obj):
        colors = {
            'iniciado': '#3498db',
            'em_andamento': '#2ecc71',
            'pausado': '#f39c12',
            'completado': '#27ae60',
            'abandonado': '#e74c3c',
            'erro': '#c0392b',
            'cancelado': '#95a5a6',
            'aguardando_validacao': '#8e44ad',
            'validado': '#16a085',
            'rejeitado': '#d35400',
        }
        color = colors.get(obj.status, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def get_progresso_display(self, obj):
        try:
            progresso = obj.get_progresso_percentual()
        except (TypeError, AttributeError):
            progresso = 0
            
        if progresso == 0:
            color = '#95a5a6'
        elif progresso < 50:
            color = '#e74c3c'
        elif progresso < 80:
            color = '#f39c12'
        else:
            color = '#2ecc71'
        
        return format_html(
            '<div style="background:#f8f9fa;padding:4px;border-radius:4px;border:1px solid #dee2e6;">'
            '<div style="background:{};height:20px;border-radius:3px;width:{}%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:bold;">'
            '{}%</div></div>',
            color, progresso, progresso
        )
    get_progresso_display.short_description = 'Progresso'
    
    def get_tempo_formatado(self, obj):
        try:
            return obj.get_tempo_formatado()
        except (TypeError, AttributeError):
            return "N/A"
    get_tempo_formatado.short_description = 'Tempo'
    get_tempo_formatado.admin_order_field = 'tempo_total'
    
    def get_respostas_formatadas_display(self, obj):
        if not obj.pk:
            return "Salve o atendimento para ver respostas"
        
        try:
            respostas = obj.get_respostas_formatadas()
        except (TypeError, AttributeError):
            return "Erro ao carregar respostas"
            
        if not respostas:
            return "Nenhuma resposta registrada"
        
        html = '<div style="background:#f8f9fa;padding:15px;border-radius:8px;border:1px solid #dee2e6;">'
        html += '<h4 style="margin-top:0;color:#495057;">📝 Respostas do Usuário</h4>'
        
        for resp in respostas:
            status_icon = "✅" if resp['respondida'] else "❌"
            status_color = "#2ecc71" if resp['respondida'] else "#e74c3c"
            
            html += f'''
            <div style="margin-bottom:10px;padding:10px;background:#fff;border-radius:6px;border-left:4px solid {status_color};">
                <strong>{status_icon} Q{resp['indice']}: {resp['questao']}</strong><br>
                <span style="color:#666;font-size:12px;">Resposta: {resp['resposta']}</span><br>
                <span style="color:#999;font-size:11px;">Data: {resp['data_resposta'] or 'Não respondida'}</span>
            </div>
            '''
        
        html += '</div>'
        return format_html(html)
    get_respostas_formatadas_display.short_description = 'Respostas'
    
    def get_estatisticas_display(self, obj):
        if not obj.pk:
            return "Salve o atendimento para ver estatísticas"
        
        try:
            progresso = obj.get_progresso_percentual()
            tempo_formatado = obj.get_tempo_formatado()
        except (TypeError, AttributeError):
            progresso = 0
            tempo_formatado = "N/A"
        
        html = f'''
        <div style="background:#f8f9fa;padding:15px;border-radius:8px;border:1px solid #dee2e6;">
            <h4 style="margin-top:0;color:#495057;">📊 Estatísticas do Atendimento</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                <div>
                    <strong>Status:</strong> {obj.get_status_display()}<br>
                    <strong>Questão Atual:</strong> {obj.questao_atual}<br>
                    <strong>Progresso:</strong> {progresso}%
                </div>
                <div>
                    <strong>Questões Respondidas:</strong> {obj.questoes_respondidas}/{obj.total_questoes}<br>
                    <strong>Tempo Total:</strong> {tempo_formatado}<br>
                    <strong>Score:</strong> {obj.score_qualificacao or 'N/A'}/10
                </div>
            </div>
        </div>
        '''
        return format_html(html)
    get_estatisticas_display.short_description = 'Estatísticas'
    
    def get_estatisticas_tentativas_display(self, obj):
        if not obj.pk:
            return "Salve o atendimento para ver estatísticas de tentativas"
        
        try:
            stats = obj.get_estatisticas_tentativas()
        except (TypeError, AttributeError):
            return "Erro ao carregar estatísticas"
        
        html = f'''
        <div style="background:#e8f5e8;padding:15px;border-radius:8px;border:1px solid #c3e6c3;">
            <h4 style="margin-top:0;color:#2d5a2d;">🤖 Estatísticas de Tentativas Inteligentes</h4>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                <div>
                    <strong>Total de Tentativas:</strong> {stats['total_tentativas']}<br>
                    <strong>Respostas Válidas:</strong> {stats['respostas_validas']}<br>
                    <strong>Respostas Inválidas:</strong> {stats['respostas_invalidas']}<br>
                    <strong>Taxa de Sucesso:</strong> {stats['taxa_sucesso']}%
                </div>
                <div>
                    <strong>Questões com Múltiplas Tentativas:</strong> {stats['questoes_multiplas_tentativas']}<br>
                    <strong>Tentativas Médias por Questão:</strong> {stats['tentativas_medias']}<br>
                    <strong>Tentativas com IA:</strong> {stats['tentativas_ia']}<br>
                    <strong>Estratégias Aplicadas:</strong> {stats['estrategias_aplicadas']}
                </div>
            </div>
        </div>
        '''
        return format_html(html)
    get_estatisticas_tentativas_display.short_description = 'Tentativas Inteligentes'
    
    # Ações em massa
    def reiniciar_atendimentos(self, request, queryset):
        count = 0
        for atendimento in queryset:
            if atendimento.pode_ser_reiniciado():
                if atendimento.reiniciar_atendimento():
                    count += 1
        
        if count > 0:
            self.message_user(request, f"{count} atendimento(s) reiniciado(s) com sucesso.")
        else:
            self.message_user(request, "Nenhum atendimento pode ser reiniciado.")
    reiniciar_atendimentos.short_description = 'Reiniciar selecionados'
    
    def finalizar_atendimentos(self, request, queryset):
        count = 0
        for atendimento in queryset:
            if atendimento.status not in ['completado', 'abandonado', 'cancelado']:
                atendimento.finalizar_atendimento(sucesso=True)
                count += 1
        
        if count > 0:
            self.message_user(request, f"{count} atendimento(s) finalizado(s) com sucesso.")
        else:
            self.message_user(request, "Nenhum atendimento pode ser finalizado.")
    finalizar_atendimentos.short_description = 'Finalizar selecionados'
    
    def calcular_scores(self, request, queryset):
        count = 0
        for atendimento in queryset:
            if atendimento.status == 'completado' and not atendimento.score_qualificacao:
                atendimento.atualizar_score_conversao()
                count += 1
        
        if count > 0:
            self.message_user(request, f"{count} score(s) calculado(s) com sucesso.")
        else:
            self.message_user(request, "Nenhum score pode ser calculado.")
    calcular_scores.short_description = 'Calcular scores'


@admin.register(TentativaResposta)
class TentativaRespostaAdmin(admin.ModelAdmin):
    list_display = [
        'atendimento',
        'questao',
        'tentativa_numero',
        'valida_badge',
        'confianca_ia',
        'estrategia_aplicada',
        'tempo_resposta_formatado',
        'data_tentativa'
    ]
    list_filter = [
        'valida',
        'estrategia_aplicada',
        'data_tentativa',
        'questao__tipo_questao',
        'atendimento__fluxo'
    ]
    search_fields = [
        'resposta_original',
        'atendimento__lead__nome_razaosocial',
        'questao__titulo'
    ]
    readonly_fields = [
        'data_tentativa',
        'tempo_resposta_segundos',
        'ip_origem',
        'user_agent',
        'get_resultado_ia_resumido'
    ]
    fieldsets = (
        ('Tentativa', {
            'fields': (
                'atendimento',
                'questao',
                'tentativa_numero',
                'resposta_original',
                'resposta_processada'
            )
        }),
        ('Validação', {
            'fields': (
                'valida',
                'mensagem_erro',
                'estrategia_aplicada'
            )
        }),
        ('IA e Webhooks', {
            'fields': (
                'resultado_ia',
                'confianca_ia',
                'resultado_webhook',
                'get_resultado_ia_resumido'
            ),
            'classes': ('collapse',)
        }),
        ('Contexto', {
            'fields': (
                'contexto_tentativa',
                'data_tentativa',
                'tempo_resposta_segundos'
            ),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': (
                'ip_origem',
                'user_agent'
            ),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'data_tentativa'
    ordering = ['-data_tentativa']
    list_per_page = 25
    autocomplete_fields = ['atendimento', 'questao']
    list_select_related = ['atendimento', 'questao', 'atendimento__lead', 'atendimento__fluxo']
    save_on_top = True
    
    def valida_badge(self, obj):
        if obj.valida:
            return format_html('<span style="color:#2ecc71;font-weight:600;">✓ Válida</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">✗ Inválida</span>')
    valida_badge.short_description = 'Válida'
    valida_badge.admin_order_field = 'valida'
    
    def tempo_resposta_formatado(self, obj):
        try:
            return obj.get_tempo_resposta_formatado()
        except (TypeError, AttributeError):
            return "N/A"
    tempo_resposta_formatado.short_description = 'Tempo'
    tempo_resposta_formatado.admin_order_field = 'tempo_resposta_segundos'
    
    def get_resultado_ia_resumido(self, obj):
        try:
            return obj.get_resultado_ia_resumido()
        except (TypeError, AttributeError):
            return "N/A"
    get_resultado_ia_resumido.short_description = 'IA Resumo'


@admin.register(RespostaQuestao)
class RespostaQuestaoAdmin(admin.ModelAdmin):
    list_display = [
        'atendimento',
        'questao',
        'resposta_truncada',
        'valida_badge',
        'tentativas',
        'get_tempo_resposta_formatado',
        'data_resposta'
    ]
    list_filter = [
        'valida',
        'tentativas',
        'data_resposta',
        'questao__tipo_questao',
        'atendimento__fluxo'
    ]
    search_fields = [
        'resposta',
        'atendimento__lead__nome_razaosocial',
        'questao__titulo'
    ]
    readonly_fields = [
        'data_resposta',
        'get_tempo_resposta_formatado'
    ]
    fieldsets = (
        ('Resposta', {
            'fields': (
                'atendimento',
                'questao',
                'resposta',
                'resposta_processada'
            )
        }),
        ('Validação', {
            'fields': (
                'valida',
                'mensagem_erro',
                'tentativas'
            )
        }),
        ('Tempo', {
            'fields': (
                'data_resposta',
                'tempo_resposta',
                'get_tempo_resposta_formatado'
            )
        }),
        ('Auditoria', {
            'fields': (
                'ip_origem',
                'user_agent',
                'dados_extras'
            ),
            'classes': ('collapse',)
        })
    )
    date_hierarchy = 'data_resposta'
    ordering = ['-data_resposta']
    list_per_page = 25
    autocomplete_fields = ['atendimento', 'questao']
    list_select_related = ['atendimento', 'questao', 'atendimento__lead', 'atendimento__fluxo']
    save_on_top = True
    
    def resposta_truncada(self, obj):
        if len(obj.resposta) > 50:
            return f"{obj.resposta[:50]}..."
        return obj.resposta
    resposta_truncada.short_description = 'Resposta'
    resposta_truncada.admin_order_field = 'resposta'
    
    def valida_badge(self, obj):
        if obj.valida:
            return format_html('<span style="color:#2ecc71;font-weight:600;">✓ Válida</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">✗ Inválida</span>')
    valida_badge.short_description = 'Válida'
    valida_badge.admin_order_field = 'valida'
    
    def get_tempo_resposta_formatado(self, obj):
        try:
            return obj.get_tempo_resposta_formatado()
        except (TypeError, AttributeError):
            return "N/A"
    get_tempo_resposta_formatado.short_description = 'Tempo de Resposta'
    get_tempo_resposta_formatado.admin_order_field = 'tempo_resposta'

# ============================================================================
# ADMIN PARA MODELOS DE CADASTRO
# ============================================================================

@admin.register(ConfiguracaoCadastro)
class ConfiguracaoCadastroAdmin(admin.ModelAdmin):
    list_display = [
        'empresa',
        'titulo_pagina',
        'mostrar_selecao_plano',
        'criar_lead_automatico',
        'ativo',
        'data_atualizacao'
    ]
    list_filter = [
        'ativo',
        'mostrar_selecao_plano',
        'criar_lead_automatico',
        'validar_cep',
        'validar_cpf'
    ]
    search_fields = ['empresa', 'titulo_pagina']
    readonly_fields = ['data_criacao', 'data_atualizacao']
    
    fieldsets = (
        ('🏢 Configurações Gerais', {
            'fields': [
                'empresa',
                'titulo_pagina',
                'subtitulo_pagina',
                'ativo'
            ],
            'description': 'Configurações básicas da página de cadastro'
        }),
        ('🎨 Configurações Visuais', {
            'fields': [
                'logo_url',
                'background_type',
                'background_color_1',
                'background_color_2',
                'background_image_url',
                'primary_color',
                'secondary_color',
                'success_color',
                'error_color'
            ],
            'description': 'Personalize as cores e aparência da página de cadastro',
            'classes': ('collapse',)
        }),
        ('📞 Contato e Suporte', {
            'fields': [
                'telefone_suporte',
                'whatsapp_suporte',
                'email_suporte'
            ],
            'description': 'Canais de contato exibidos na página'
        }),
        ('💳 Configurações de Planos', {
            'fields': [
                'mostrar_selecao_plano',
                'plano_padrao'
            ],
            'description': 'Configure a seleção de planos na página'
        }),
        ('✅ Campos Obrigatórios', {
            'fields': [
                'cpf_obrigatorio',
                'email_obrigatorio',
                'telefone_obrigatorio',
                'endereco_obrigatorio'
            ],
            'description': 'Defina quais campos são obrigatórios'
        }),
        ('🔍 Validações', {
            'fields': [
                'validar_cep',
                'validar_cpf'
            ],
            'description': 'Configure validações automáticas'
        }),
        ('📄 Configurações de Documentação', {
            'fields': [
                'solicitar_documentacao',
                'texto_instrucao_selfie',
                'texto_instrucao_doc_frente',
                'texto_instrucao_doc_verso',
                'tamanho_max_arquivo_mb',
                'formatos_aceitos'
            ],
            'description': 'Configure os requisitos para upload de documentos',
            'classes': ('collapse',)
        }),
        ('📋 Configurações de Contrato', {
            'fields': [
                'exibir_contrato',
                'titulo_contrato',
                'texto_contrato',
                'tempo_minimo_leitura_segundos',
                'texto_aceite_contrato'
            ],
            'description': 'Configure o contrato e termos de serviço',
            'classes': ('collapse',)
        }),
        ('🔄 Configurações de Fluxo', {
            'fields': [
                'mostrar_progress_bar',
                'numero_etapas'
            ],
            'description': 'Configure a experiência do usuário'
        }),
        ('💬 Mensagens', {
            'fields': [
                'mensagem_sucesso',
                'instrucoes_pos_cadastro'
            ],
            'description': 'Mensagens exibidas ao usuário'
        }),
        ('🔗 Integração', {
            'fields': [
                'criar_lead_automatico',
                'origem_lead_padrao',
                'id_origem',
                'id_origem_servico',
                'id_vendedor'
            ],
            'description': 'Configure integrações com o sistema e IDs de rastreamento'
        }),
        ('🔔 Notificações', {
            'fields': [
                'enviar_email_confirmacao',
                'enviar_whatsapp_confirmacao'
            ],
            'description': 'Configure notificações automáticas'
        }),
        ('🔒 Segurança', {
            'fields': [
                'captcha_obrigatorio',
                'limite_tentativas_dia'
            ],
            'description': 'Configurações de segurança e proteção'
        }),
        ('🔧 Metadados', {
            'fields': [
                'data_criacao',
                'data_atualizacao'
            ],
            'classes': ('collapse',),
            'description': 'Informações técnicas do sistema'
        })
    )
    
    save_on_top = True


@admin.register(PlanoInternet)
class PlanoInternetAdmin(admin.ModelAdmin):
    list_display = [
        'nome',
        'velocidade_download',
        'velocidade_upload',
        'valor_mensal',
        'destaque',
        'ativo',
        'ordem_exibicao'
    ]
    list_filter = [
        'ativo',
        'destaque',
        'wifi_6',
        'suporte_prioritario',
        'suporte_24h',
        'upload_simetrico'
    ]
    search_fields = ['nome', 'descricao']
    list_editable = ['ativo', 'ordem_exibicao']
    readonly_fields = ['data_criacao', 'data_atualizacao']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': [
                'nome',
                'descricao',
                'ativo'
            ]
        }),
        ('Velocidades', {
            'fields': [
                'velocidade_download',
                'velocidade_upload',
                'upload_simetrico'
            ]
        }),
        ('Preço', {
            'fields': [
                'valor_mensal',
                'id_sistema_externo'
            ]
        }),
        ('Características', {
            'fields': [
                'wifi_6',
                'suporte_prioritario',
                'suporte_24h'
            ]
        }),
        ('Exibição', {
            'fields': [
                'destaque',
                'ordem_exibicao'
            ]
        }),
        ('Metadados', {
            'fields': [
                'data_criacao',
                'data_atualizacao'
            ],
            'classes': ('collapse',)
        })
    )
    
    save_on_top = True


@admin.register(OpcaoVencimento)
class OpcaoVencimentoAdmin(admin.ModelAdmin):
    list_display = [
        'dia_vencimento',
        'descricao',
        'ordem_exibicao',
        'ativo'
    ]
    list_filter = ['ativo']
    list_editable = ['ativo', 'ordem_exibicao']
    ordering = ['ordem_exibicao', 'dia_vencimento']
    
    fieldsets = (
        ('Configuração', {
            'fields': [
                'dia_vencimento',
                'descricao',
                'ordem_exibicao',
                'ativo'
            ]
        }),
    )


@admin.register(CadastroCliente)
class CadastroClienteAdmin(admin.ModelAdmin):
    list_display = [
        'nome_completo',
        'email',
        'telefone',
        'plano_selecionado',
        'status',
        'data_inicio',
        'lead_gerado'
    ]
    list_filter = [
        'status',
        'origem_cadastro',
        'data_inicio',
        'plano_selecionado'
    ]
    search_fields = [
        'nome_completo',
        'cpf',
        'email',
        'telefone',
        'cidade'
    ]
    readonly_fields = [
        'data_inicio',
        'data_finalizacao',
        'tempo_total_cadastro',
        'ip_cliente',
        'user_agent',
        'get_progresso_percentual',
        'get_etapa_atual'
    ]
    
    fieldsets = (
        ('Dados Pessoais', {
            'fields': [
                'nome_completo',
                'cpf',
                'email',
                'telefone',
                'data_nascimento'
            ]
        }),
        ('Endereço', {
            'fields': [
                'cep',
                'endereco',
                'numero',
                'bairro',
                'cidade',
                'estado'
            ]
        }),
        ('Plano e Vencimento', {
            'fields': [
                'plano_selecionado',
                'vencimento_selecionado'
            ]
        }),
        ('Status e Progresso', {
            'fields': [
                'status',
                'get_progresso_percentual',
                'get_etapa_atual',
                'data_inicio',
                'data_finalizacao',
                'tempo_total_cadastro'
            ]
        }),
        ('Integração', {
            'fields': [
                'lead_gerado',
                'origem_cadastro'
            ]
        }),
        ('Metadados', {
            'fields': [
                'ip_cliente',
                'user_agent'
            ],
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': [
                'tentativas_etapa',
                'campos_preenchidos',
                'erros_validacao'
            ],
            'classes': ('collapse',)
        })
    )
    
    actions = ['finalizar_cadastro', 'gerar_lead']
    
    def finalizar_cadastro(self, request, queryset):
        """Ação para finalizar cadastros selecionados"""
        count = 0
        for cadastro in queryset:
            if cadastro.status != 'finalizado':
                if cadastro.finalizar_cadastro():
                    count += 1
        
        self.message_user(
            request,
            f'{count} cadastro(s) finalizado(s) com sucesso.'
        )
    finalizar_cadastro.short_description = "Finalizar cadastros selecionados"
    
    def gerar_lead(self, request, queryset):
        """Ação para gerar leads para cadastros selecionados"""
        count = 0
        for cadastro in queryset:
            if not cadastro.lead_gerado:
                if cadastro.gerar_lead():
                    count += 1
        
        self.message_user(
            request,
            f'{count} lead(s) gerado(s) com sucesso.'
        )
    gerar_lead.short_description = "Gerar leads para cadastros selecionados"
    
    save_on_top = True


@admin.register(DocumentoLead)
class DocumentoLeadAdmin(admin.ModelAdmin):
    list_display = [
        'lead',
        'tipo_documento',
        'status_badge',
        'nome_arquivo',
        'tamanho_arquivo',
        'formato_arquivo',
        'data_upload',
        'validado_por'
    ]
    list_filter = [
        'tipo_documento',
        'status',
        'formato_arquivo',
        'data_upload',
        'data_validacao'
    ]
    search_fields = [
        'lead__nome_razaosocial',
        'lead__email',
        'lead__cpf_cnpj',
        'nome_arquivo',
        'validado_por'
    ]
    readonly_fields = [
        'data_upload',
        'data_validacao',
        'visualizar_documento',
        'tamanho_formatado',
        'get_lead_info'
    ]
    
    fieldsets = (
        ('Informações do Documento', {
            'fields': [
                'lead',
                'tipo_documento',
                'status',
                'get_lead_info'
            ]
        }),
        ('Arquivo', {
            'fields': [
                'nome_arquivo',
                'formato_arquivo',
                'tamanho_arquivo',
                'tamanho_formatado',
                'visualizar_documento'
            ]
        }),
        ('Validação', {
            'fields': [
                'observacoes_validacao',
                'validado_por',
                'data_validacao'
            ]
        }),
        ('Dados do Arquivo', {
            'fields': [
                'arquivo_base64'
            ],
            'classes': ('collapse',),
            'description': 'Dados da imagem em base64'
        }),
        ('Metadados', {
            'fields': [
                'data_upload'
            ]
        })
    )
    
    autocomplete_fields = ['lead']
    list_select_related = ['lead']
    date_hierarchy = 'data_upload'
    list_per_page = 25
    save_on_top = True
    actions = ['aprovar_documentos', 'rejeitar_documentos']
    
    def status_badge(self, obj):
        colors = {
            'pendente': '#f39c12',
            'aprovado': '#2ecc71',
            'rejeitado': '#e74c3c',
            'em_analise': '#3498db'
        }
        color = colors.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def tamanho_formatado(self, obj):
        """Retorna o tamanho formatado do arquivo"""
        if obj.tamanho_arquivo:
            size_kb = obj.tamanho_arquivo / 1024
            if size_kb < 1024:
                return f"{size_kb:.1f} KB"
            size_mb = size_kb / 1024
            return f"{size_mb:.1f} MB"
        return "N/A"
    tamanho_formatado.short_description = "Tamanho"
    
    def visualizar_documento(self, obj):
        """Campo para visualizar o documento"""
        if obj.arquivo_base64:
            return format_html(
                '''
                <div style="text-align:center;">
                    <img src="data:image/{};base64,{}" style="max-width:400px;max-height:300px;border:1px solid #ddd;border-radius:8px;cursor:pointer;" 
                         onclick="window.open('data:image/{};base64,{}', '_blank');" />
                    <br>
                    <a href="#" onclick="window.open('data:image/{};base64,{}', '_blank'); return false;" 
                       style="color:#3498db;text-decoration:none;margin-top:10px;display:inline-block;">
                       <i class="fas fa-external-link-alt"></i> Abrir em nova aba
                    </a>
                </div>
                ''',
                obj.formato_arquivo, obj.arquivo_base64[:200] + '...',
                obj.formato_arquivo, obj.arquivo_base64,
                obj.formato_arquivo, obj.arquivo_base64
            )
        return "Nenhuma imagem disponível"
    visualizar_documento.short_description = "Documento"
    
    def get_lead_info(self, obj):
        """Retorna informações formatadas do lead"""
        if obj.lead:
            return format_html(
                '''
                <div style="background:#f8f9fa;padding:10px;border-radius:6px;border:1px solid #dee2e6;">
                    <strong>Nome:</strong> {}<br>
                    <strong>CPF/CNPJ:</strong> {}<br>
                    <strong>Email:</strong> {}<br>
                    <strong>Telefone:</strong> {}
                </div>
                ''',
                obj.lead.nome_razaosocial,
                obj.lead.cpf_cnpj or 'N/A',
                obj.lead.email or 'N/A',
                obj.lead.telefone
            )
        return "N/A"
    get_lead_info.short_description = "Informações do Lead"
    
    def aprovar_documentos(self, request, queryset):
        """Ação para aprovar documentos selecionados"""
        count = 0
        for doc in queryset.filter(status__in=['pendente', 'em_analise']):
            doc.validar_documento(
                status='aprovado',
                observacoes='Aprovado via admin',
                usuario=request.user.username if request.user.is_authenticated else 'admin'
            )
            count += 1
        
        # Verificar se o lead tem todos os documentos aprovados
        for lead in set(doc.lead for doc in queryset):
            if lead:
                docs_obrigatorios = ['selfie', 'doc_frente', 'doc_verso']
                todos_aprovados = all(
                    lead.documentos.filter(tipo_documento=tipo, status='aprovado').exists()
                    for tipo in docs_obrigatorios
                )
                
                if todos_aprovados and not lead.documentacao_validada:
                    lead.documentacao_validada = True
                    lead.data_documentacao_validada = timezone.now()
                    lead.save()
        
        self.message_user(request, f"{count} documento(s) aprovado(s) com sucesso.")
    aprovar_documentos.short_description = "Aprovar documentos selecionados"
    
    def rejeitar_documentos(self, request, queryset):
        """Ação para rejeitar documentos selecionados"""
        count = 0
        for doc in queryset.exclude(status='rejeitado'):
            doc.validar_documento(
                status='rejeitado',
                observacoes='Rejeitado via admin',
                usuario=request.user.username if request.user.is_authenticated else 'admin'
            )
            count += 1
        
        self.message_user(request, f"{count} documento(s) rejeitado(s).")
    rejeitar_documentos.short_description = "Rejeitar documentos selecionados"


@admin.register(ConfiguracaoEmpresa)
class ConfiguracaoEmpresaAdmin(admin.ModelAdmin):
    list_display = ('nome_empresa_badge', 'cores_preview', 'ativo_badge', 'data_criacao_formatada')
    list_filter = ('ativo', 'data_criacao')
    search_fields = ('nome_empresa',)
    readonly_fields = ('data_criacao', 'data_atualizacao', 'preview_cores', 'preview_logo')
    
    fieldsets = (
        ('🏢 Informações da Empresa', {
            'fields': ('nome_empresa', 'logo_empresa', 'preview_logo'),
            'description': 'Configure a logomarca que aparecerá na tela de login. Formatos suportados: PNG, JPG, SVG. Fundo transparente (PNG) fica melhor sobre o gradiente.',
        }),
        ('🎨 Personalização Visual', {
            'fields': ('cor_primaria', 'cor_secundaria', 'preview_cores'),
            'description': 'Configure as cores do sistema. Use formato HEX (ex: #1F3D59)'
        }),
        ('✅ Status da Configuração', {
            'fields': ('ativo',),
            'description': 'Apenas uma configuração pode estar ativa por vez'
        }),
        ('📊 Informações do Sistema', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-ativo', '-data_criacao')
    
    def save_model(self, request, obj, form, change):
        # Se esta configuração está sendo ativada, desativar as outras
        if obj.ativo:
            ConfiguracaoEmpresa.objects.filter(ativo=True).exclude(id=obj.id).update(ativo=False)
        super().save_model(request, obj, form, change)
    
    def preview_logo(self, obj):
        if obj.logo_empresa:
            return format_html(
                '<div style="background:linear-gradient(135deg,{} 0%,{} 100%);'
                'padding:24px;border-radius:12px;display:inline-flex;align-items:center;justify-content:center;">'
                '<img src="{}" style="max-width:220px;max-height:160px;object-fit:contain;'
                'filter:drop-shadow(0 4px 12px rgba(0,0,0,0.2));" alt="Preview da logo"></div>'
                '<p style="margin-top:6px;font-size:11px;color:#888;">Preview como aparece na tela de login</p>',
                obj.cor_primaria, obj.cor_secundaria, obj.logo_empresa.url,
            )
        return format_html('<span style="color:#aaa;font-size:12px;">Nenhuma logo carregada ainda.</span>')
    preview_logo.short_description = '👁 Preview na tela de login'

    def nome_empresa_badge(self, obj):
        status_color = '#2ecc71' if obj.ativo else '#95a5a6'
        status_text = 'ATIVA' if obj.ativo else 'INATIVA'
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;">'
            '<strong style="color: #333;">{}</strong>'
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: bold;">{}</span>'
            '</div>',
            obj.nome_empresa, status_color, status_text
        )
    nome_empresa_badge.short_description = '🏢 Empresa'
    nome_empresa_badge.admin_order_field = 'nome_empresa'
    
    def cores_preview(self, obj):
        return format_html(
            '<div style="display: flex; gap: 5px; align-items: center;">'
            '<div style="width: 20px; height: 20px; background: {}; border-radius: 4px; border: 1px solid #ddd;"></div>'
            '<div style="width: 20px; height: 20px; background: {}; border-radius: 4px; border: 1px solid #ddd;"></div>'
            '<span style="font-size: 11px; color: #666; margin-left: 5px;">Primária | Secundária</span>'
            '</div>',
            obj.cor_primaria, obj.cor_secundaria
        )
    cores_preview.short_description = '🎨 Cores'
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html(
                '<span style="background: #2ecc71; color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold;">'
                '✓ CONFIGURAÇÃO ATIVA</span>'
            )
        return format_html(
            '<span style="background: #95a5a6; color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold;">'
            '○ Inativa</span>'
        )
    ativo_badge.short_description = '⚡ Status'
    ativo_badge.admin_order_field = 'ativo'
    
    def data_criacao_formatada(self, obj):
        return obj.data_criacao.strftime('%d/%m/%Y às %H:%M')
    data_criacao_formatada.short_description = '📅 Criada em'
    data_criacao_formatada.admin_order_field = 'data_criacao'
    
    def preview_cores(self, obj):
        if obj.cor_primaria and obj.cor_secundaria:
            return format_html(
                '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #dee2e6;">'
                '<h4 style="margin: 0 0 15px 0; color: #495057;">🎨 Preview das Cores</h4>'
                '<div style="display: flex; gap: 20px; align-items: center;">'
                '<div style="text-align: center;">'
                '<div style="width: 60px; height: 60px; background: {}; border-radius: 8px; border: 2px solid #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"></div>'
                '<p style="margin: 8px 0 0 0; font-size: 12px; color: #666;"><strong>Primária</strong><br>{}</p>'
                '</div>'
                '<div style="text-align: center;">'
                '<div style="width: 60px; height: 60px; background: {}; border-radius: 8px; border: 2px solid #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"></div>'
                '<p style="margin: 8px 0 0 0; font-size: 12px; color: #666;"><strong>Secundária</strong><br>{}</p>'
                '</div>'
                '<div style="margin-left: 20px;">'
                '<p style="margin: 0; font-size: 13px; color: #495057;"><strong>Como ficará no sistema:</strong></p>'
                '<div style="margin-top: 10px; padding: 10px; background: white; border-radius: 4px; border: 1px solid #dee2e6;">'
                '<div style="color: {}; font-weight: 600; margin-bottom: 5px;">Elementos Ativos</div>'
                '<div style="background: {}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; display: inline-block;">Botão Primário</div>'
                '</div>'
                '</div>'
                '</div>'
                '</div>',
                obj.cor_primaria, obj.cor_primaria,
                obj.cor_secundaria, obj.cor_secundaria,
                obj.cor_primaria, obj.cor_primaria
            )
        return "Configure as cores para ver o preview"
    preview_cores.short_description = '🎨 Preview Visual'


# ============================================================================
# ADMIN PARA SISTEMA DE NOTIFICAÇÕES
# ============================================================================

@admin.register(TipoNotificacao)
class TipoNotificacaoAdmin(admin.ModelAdmin):
    list_display = [
        'nome',
        'codigo',
        'prioridade_padrao_badge',
        'ativo_badge',
        'get_total_notificacoes'
    ]
    list_filter = [
        'ativo',
        'prioridade_padrao',
        'codigo'
    ]
    search_fields = [
        'nome',
        'codigo',
        'descricao'
    ]
    readonly_fields = [
        'get_total_notificacoes',
        'get_templates_ativos'
    ]
    fieldsets = (
        ('📢 Informações Básicas', {
            'fields': (
                'codigo',
                'nome',
                'descricao',
                'ativo'
            ),
            'description': 'Configure as informações básicas do tipo de notificação'
        }),
        ('⚙️ Configurações Padrão', {
            'fields': (
                'prioridade_padrao',
                'template_padrao'
            ),
            'description': 'Defina configurações padrão para este tipo'
        }),
        ('📊 Estatísticas', {
            'fields': (
                'get_total_notificacoes',
                'get_templates_ativos'
            ),
            'classes': ('collapse',),
            'description': 'Estatísticas de uso deste tipo de notificação'
        })
    )
    ordering = ['nome']
    list_per_page = 25
    save_on_top = True
    actions = ['ativar_tipos', 'inativar_tipos']
    
    def prioridade_padrao_badge(self, obj):
        colors = {
            'baixa': '#95a5a6',
            'normal': '#3498db',
            'alta': '#f39c12',
            'urgente': '#e74c3c'
        }
        color = colors.get(obj.prioridade_padrao, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;font-size:11px;">{}</span>',
            color, obj.get_prioridade_padrao_display()
        )
    prioridade_padrao_badge.short_description = 'Prioridade'
    prioridade_padrao_badge.admin_order_field = 'prioridade_padrao'
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color:#2ecc71;font-weight:600;">✓ Ativo</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">✗ Inativo</span>')
    ativo_badge.short_description = 'Status'
    ativo_badge.admin_order_field = 'ativo'
    
    def get_total_notificacoes(self, obj):
        if not obj.pk:
            return "0"
        try:
            total = obj.notificacao_set.count()
            return f"{total} notificações"
        except:
            return "0"
    get_total_notificacoes.short_description = 'Total de Notificações'
    
    def get_templates_ativos(self, obj):
        if not obj.pk:
            return "0"
        try:
            total = obj.templatenotificacao_set.filter(ativo=True).count()
            return f"{total} templates ativos"
        except:
            return "0"
    get_templates_ativos.short_description = 'Templates Ativos'
    
    def ativar_tipos(self, request, queryset):
        updated = queryset.update(ativo=True)
        self.message_user(request, f"{updated} tipo(s) ativado(s).")
    ativar_tipos.short_description = 'Ativar selecionados'
    
    def inativar_tipos(self, request, queryset):
        updated = queryset.update(ativo=False)
        self.message_user(request, f"{updated} tipo(s) inativado(s).")
    inativar_tipos.short_description = 'Inativar selecionados'


@admin.register(CanalNotificacao)
class CanalNotificacaoAdmin(admin.ModelAdmin):
    list_display = [
        'nome',
        'codigo',
        'icone_display',
        'ativo_badge',
        'get_total_notificacoes'
    ]
    list_filter = [
        'ativo',
        'codigo'
    ]
    search_fields = [
        'nome',
        'codigo'
    ]
    readonly_fields = [
        'get_total_notificacoes',
        'get_templates_ativos',
        'configuracao_formatada'
    ]
    fieldsets = (
        ('📱 Informações Básicas', {
            'fields': (
                'codigo',
                'nome',
                'icone',
                'ativo'
            ),
            'description': 'Configure as informações básicas do canal'
        }),
        ('⚙️ Configurações', {
            'fields': (
                'configuracao',
                'configuracao_formatada'
            ),
            'description': 'Configurações específicas do canal (JSON)'
        }),
        ('📊 Estatísticas', {
            'fields': (
                'get_total_notificacoes',
                'get_templates_ativos'
            ),
            'classes': ('collapse',),
            'description': 'Estatísticas de uso deste canal'
        })
    )
    ordering = ['nome']
    list_per_page = 25
    save_on_top = True
    actions = ['ativar_canais', 'inativar_canais']
    
    def icone_display(self, obj):
        return format_html('<i class="{}"></i> {}', obj.icone, obj.icone)
    icone_display.short_description = 'Ícone'
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color:#2ecc71;font-weight:600;">✓ Ativo</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">✗ Inativo</span>')
    ativo_badge.short_description = 'Status'
    ativo_badge.admin_order_field = 'ativo'
    
    def get_total_notificacoes(self, obj):
        if not obj.pk:
            return "0"
        try:
            total = obj.notificacao_set.count()
            return f"{total} notificações"
        except:
            return "0"
    get_total_notificacoes.short_description = 'Total de Notificações'
    
    def get_templates_ativos(self, obj):
        if not obj.pk:
            return "0"
        try:
            total = obj.templatenotificacao_set.filter(ativo=True).count()
            return f"{total} templates ativos"
        except:
            return "0"
    get_templates_ativos.short_description = 'Templates Ativos'
    
    def configuracao_formatada(self, obj):
        if obj.configuracao:
            try:
                import json
                config_json = json.dumps(obj.configuracao, indent=2, ensure_ascii=False)
                return format_html(
                    '<pre style="background:#f8f9fa;padding:10px;border-radius:4px;border:1px solid #dee2e6;font-size:12px;">{}</pre>',
                    config_json
                )
            except:
                return str(obj.configuracao)
        return "Nenhuma configuração"
    configuracao_formatada.short_description = 'Configuração (Formatada)'
    
    def ativar_canais(self, request, queryset):
        updated = queryset.update(ativo=True)
        self.message_user(request, f"{updated} canal(is) ativado(s).")
    ativar_canais.short_description = 'Ativar selecionados'
    
    def inativar_canais(self, request, queryset):
        updated = queryset.update(ativo=False)
        self.message_user(request, f"{updated} canal(is) inativado(s).")
    inativar_canais.short_description = 'Inativar selecionados'


@admin.register(PreferenciaNotificacao)
class PreferenciaNotificacaoAdmin(admin.ModelAdmin):
    list_display = [
        'usuario',
        'tipo_notificacao',
        'canal_preferido',
        'horario_display',
        'dias_semana_display',
        'ativo_badge'
    ]
    list_filter = [
        'ativo',
        'tipo_notificacao',
        'canal_preferido',
        'usuario'
    ]
    search_fields = [
        'usuario__username',
        'usuario__email',
        'tipo_notificacao__nome',
        'canal_preferido__nome'
    ]
    readonly_fields = [
        'dias_semana_formatados'
    ]
    fieldsets = (
        ('👤 Usuário e Notificação', {
            'fields': (
                'usuario',
                'tipo_notificacao',
                'canal_preferido',
                'ativo'
            ),
            'description': 'Configure as preferências do usuário'
        }),
        ('⏰ Horários', {
            'fields': (
                'horario_inicio',
                'horario_fim'
            ),
            'description': 'Defina os horários permitidos para recebimento'
        }),
        ('📅 Dias da Semana', {
            'fields': (
                'dias_semana',
                'dias_semana_formatados'
            ),
            'description': 'Selecione os dias da semana (0=segunda, 6=domingo)'
        })
    )
    ordering = ['usuario__username', 'tipo_notificacao__nome']
    list_per_page = 25
    save_on_top = True
    autocomplete_fields = ['usuario', 'tipo_notificacao', 'canal_preferido']
    list_select_related = ['usuario', 'tipo_notificacao', 'canal_preferido']
    actions = ['ativar_preferencias', 'inativar_preferencias']
    
    def horario_display(self, obj):
        return f"{obj.horario_inicio} - {obj.horario_fim}"
    horario_display.short_description = 'Horário'
    
    def dias_semana_display(self, obj):
        if obj.dias_semana:
            dias_nomes = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
            dias_selecionados = [dias_nomes[d] for d in obj.dias_semana if 0 <= d <= 6]
            return ', '.join(dias_selecionados)
        return "Nenhum"
    dias_semana_display.short_description = 'Dias'
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color:#2ecc71;font-weight:600;">✓ Ativo</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">✗ Inativo</span>')
    ativo_badge.short_description = 'Status'
    ativo_badge.admin_order_field = 'ativo'
    
    def dias_semana_formatados(self, obj):
        if obj.dias_semana:
            dias_nomes = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
            dias_selecionados = [f"{d} ({dias_nomes[d]})" for d in obj.dias_semana if 0 <= d <= 6]
            return format_html(
                '<div style="background:#f8f9fa;padding:10px;border-radius:4px;border:1px solid #dee2e6;">'
                '<strong>Dias selecionados:</strong><br>{}'
                '</div>',
                '<br>'.join(dias_selecionados)
            )
        return "Nenhum dia selecionado"
    dias_semana_formatados.short_description = 'Dias da Semana (Formatado)'
    
    def ativar_preferencias(self, request, queryset):
        updated = queryset.update(ativo=True)
        self.message_user(request, f"{updated} preferência(s) ativada(s).")
    ativar_preferencias.short_description = 'Ativar selecionadas'
    
    def inativar_preferencias(self, request, queryset):
        updated = queryset.update(ativo=False)
        self.message_user(request, f"{updated} preferência(s) inativada(s).")
    inativar_preferencias.short_description = 'Inativar selecionadas'


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = [
        'titulo_truncado',
        'tipo',
        'canal',
        'destinatario_display',
        'status_badge',
        'prioridade_badge',
        'data_criacao_formatada',
        'tentativas_display'
    ]
    list_filter = [
        'status',
        'prioridade',
        'tipo',
        'canal',
        'data_criacao',
        'data_envio'
    ]
    search_fields = [
        'titulo',
        'mensagem',
        'destinatario__username',
        'destinatario_email',
        'destinatario_telefone'
    ]
    readonly_fields = [
        'data_criacao',
        'data_envio',
        'tentativas',
        'n8n_response_formatado',
        'erro_detalhes',
        'dados_contexto_formatado'
    ]
    fieldsets = (
        ('📨 Informações Básicas', {
            'fields': (
                'tipo',
                'canal',
                'titulo',
                'mensagem'
            ),
            'description': 'Informações básicas da notificação'
        }),
        ('👤 Destinatário', {
            'fields': (
                'destinatario',
                'destinatario_email',
                'destinatario_telefone'
            ),
            'description': 'Informações do destinatário'
        }),
        ('⚙️ Controle', {
            'fields': (
                'status',
                'prioridade',
                'tentativas',
                'max_tentativas',
                'data_agendamento'
            ),
            'description': 'Controle de envio e status'
        }),
        ('📊 Dados de Contexto', {
            'fields': (
                'dados_contexto',
                'dados_contexto_formatado'
            ),
            'classes': ('collapse',),
            'description': 'Dados para personalização da mensagem'
        }),
        ('🔗 Integração N8N', {
            'fields': (
                'n8n_webhook_id',
                'n8n_execution_id',
                'n8n_response',
                'n8n_response_formatado'
            ),
            'classes': ('collapse',),
            'description': 'Informações da integração com N8N'
        }),
        ('❌ Erros', {
            'fields': (
                'erro_detalhes',
            ),
            'classes': ('collapse',),
            'description': 'Detalhes de erros ocorridos'
        }),
        ('📅 Timestamps', {
            'fields': (
                'data_criacao',
                'data_envio'
            ),
            'classes': ('collapse',),
            'description': 'Informações de data e hora'
        })
    )
    date_hierarchy = 'data_criacao'
    ordering = ['-data_criacao']
    list_per_page = 25
    save_on_top = True
    autocomplete_fields = ['destinatario', 'tipo', 'canal']
    list_select_related = ['tipo', 'canal', 'destinatario']
    actions = ['reprocessar_notificacoes', 'cancelar_notificacoes']
    
    def titulo_truncado(self, obj):
        if len(obj.titulo) > 50:
            return f"{obj.titulo[:50]}..."
        return obj.titulo
    titulo_truncado.short_description = 'Título'
    titulo_truncado.admin_order_field = 'titulo'
    
    def destinatario_display(self, obj):
        if obj.destinatario:
            return obj.destinatario.username
        elif obj.destinatario_email:
            return obj.destinatario_email
        elif obj.destinatario_telefone:
            return obj.destinatario_telefone
        return "N/A"
    destinatario_display.short_description = 'Destinatário'
    
    def status_badge(self, obj):
        colors = {
            'pendente': '#f39c12',
            'enviando': '#3498db',
            'enviada': '#2ecc71',
            'falhou': '#e74c3c',
            'cancelada': '#95a5a6'
        }
        color = colors.get(obj.status, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def prioridade_badge(self, obj):
        colors = {
            'baixa': '#95a5a6',
            'normal': '#3498db',
            'alta': '#f39c12',
            'urgente': '#e74c3c'
        }
        color = colors.get(obj.prioridade, '#7f8c8d')
        return format_html(
            '<span style="padding:2px 8px;border-radius:12px;background:{};color:#fff;font-size:11px;">{}</span>',
            color, obj.get_prioridade_display()
        )
    prioridade_badge.short_description = 'Prioridade'
    prioridade_badge.admin_order_field = 'prioridade'
    
    def data_criacao_formatada(self, obj):
        return obj.data_criacao.strftime('%d/%m/%Y %H:%M')
    data_criacao_formatada.short_description = 'Criada em'
    data_criacao_formatada.admin_order_field = 'data_criacao'
    
    def tentativas_display(self, obj):
        return f"{obj.tentativas}/{obj.max_tentativas}"
    tentativas_display.short_description = 'Tentativas'
    
    def dados_contexto_formatado(self, obj):
        if obj.dados_contexto:
            try:
                import json
                context_json = json.dumps(obj.dados_contexto, indent=2, ensure_ascii=False)
                return format_html(
                    '<pre style="background:#f8f9fa;padding:10px;border-radius:4px;border:1px solid #dee2e6;font-size:12px;">{}</pre>',
                    context_json
                )
            except:
                return str(obj.dados_contexto)
        return "Nenhum contexto"
    dados_contexto_formatado.short_description = 'Contexto (Formatado)'
    
    def n8n_response_formatado(self, obj):
        if obj.n8n_response:
            try:
                import json
                response_json = json.dumps(obj.n8n_response, indent=2, ensure_ascii=False)
                return format_html(
                    '<pre style="background:#e8f5e8;padding:10px;border-radius:4px;border:1px solid #c3e6c3;font-size:12px;">{}</pre>',
                    response_json
                )
            except:
                return str(obj.n8n_response)
        return "Nenhuma resposta"
    n8n_response_formatado.short_description = 'Resposta N8N (Formatada)'
    
    def reprocessar_notificacoes(self, request, queryset):
        count = 0
        for notif in queryset.filter(status__in=['falhou', 'pendente']):
            notif.status = 'pendente'
            notif.tentativas = 0
            notif.erro_detalhes = None
            notif.save()
            count += 1
        
        if count > 0:
            self.message_user(request, f"{count} notificação(ões) marcada(s) para reprocessamento.")
        else:
            self.message_user(request, "Nenhuma notificação pode ser reprocessada.")
    reprocessar_notificacoes.short_description = 'Reprocessar selecionadas'
    
    def cancelar_notificacoes(self, request, queryset):
        count = 0
        for notif in queryset.filter(status__in=['pendente', 'enviando']):
            notif.status = 'cancelada'
            notif.save()
            count += 1
        
        if count > 0:
            self.message_user(request, f"{count} notificação(ões) cancelada(s).")
        else:
            self.message_user(request, "Nenhuma notificação pode ser cancelada.")
    cancelar_notificacoes.short_description = 'Cancelar selecionadas'


@admin.register(TemplateNotificacao)
class TemplateNotificacaoAdmin(admin.ModelAdmin):
    list_display = [
        'nome',
        'tipo_notificacao',
        'canal',
        'assunto_truncado',
        'ativo_badge',
        'get_variaveis_count'
    ]
    list_filter = [
        'ativo',
        'tipo_notificacao',
        'canal'
    ]
    search_fields = [
        'nome',
        'assunto',
        'tipo_notificacao__nome',
        'canal__nome'
    ]
    readonly_fields = [
        'variaveis_formatadas',
        'preview_template'
    ]
    fieldsets = (
        ('📝 Informações Básicas', {
            'fields': (
                'tipo_notificacao',
                'canal',
                'nome',
                'ativo'
            ),
            'description': 'Configure as informações básicas do template'
        }),
        ('📧 Conteúdo', {
            'fields': (
                'assunto',
                'corpo_html',
                'corpo_texto'
            ),
            'description': 'Conteúdo do template'
        }),
        ('🔧 Variáveis', {
            'fields': (
                'variaveis',
                'variaveis_formatadas'
            ),
            'description': 'Variáveis disponíveis para personalização'
        }),
        ('👁️ Preview', {
            'fields': (
                'preview_template',
            ),
            'classes': ('collapse',),
            'description': 'Preview do template'
        })
    )
    ordering = ['tipo_notificacao__nome', 'canal__nome']
    list_per_page = 25
    save_on_top = True
    autocomplete_fields = ['tipo_notificacao', 'canal']
    list_select_related = ['tipo_notificacao', 'canal']
    actions = ['ativar_templates', 'inativar_templates']
    
    def assunto_truncado(self, obj):
        if len(obj.assunto) > 50:
            return f"{obj.assunto[:50]}..."
        return obj.assunto
    assunto_truncado.short_description = 'Assunto'
    assunto_truncado.admin_order_field = 'assunto'
    
    def ativo_badge(self, obj):
        if obj.ativo:
            return format_html('<span style="color:#2ecc71;font-weight:600;">✓ Ativo</span>')
        return format_html('<span style="color:#e74c3c;font-weight:600;">✗ Inativo</span>')
    ativo_badge.short_description = 'Status'
    ativo_badge.admin_order_field = 'ativo'
    
    def get_variaveis_count(self, obj):
        if obj.variaveis:
            return f"{len(obj.variaveis)} variáveis"
        return "0 variáveis"
    get_variaveis_count.short_description = 'Variáveis'
    
    def variaveis_formatadas(self, obj):
        if obj.variaveis:
            return format_html(
                '<div style="background:#f8f9fa;padding:10px;border-radius:4px;border:1px solid #dee2e6;">'
                '<strong>Variáveis disponíveis:</strong><br>{}'
                '</div>',
                '<br>'.join([f"• {var}" for var in obj.variaveis])
            )
        return "Nenhuma variável definida"
    variaveis_formatadas.short_description = 'Variáveis (Formatadas)'
    
    def preview_template(self, obj):
        if obj.corpo_html:
            return format_html(
                '<div style="background:#f8f9fa;padding:15px;border-radius:8px;border:1px solid #dee2e6;">'
                '<h4 style="margin-top:0;color:#495057;">📧 Preview do Template</h4>'
                '<div style="background:#fff;padding:15px;border-radius:4px;border:1px solid #ddd;">'
                '<strong>Assunto:</strong> {}<br><br>'
                '<strong>Conteúdo HTML:</strong><br>'
                '<div style="background:#f8f9fa;padding:10px;border-radius:4px;border:1px solid #dee2e6;font-family:monospace;font-size:12px;max-height:200px;overflow-y:auto;">'
                '{}'
                '</div>'
                '</div>'
                '</div>',
                obj.assunto,
                obj.corpo_html[:500] + ('...' if len(obj.corpo_html) > 500 else '')
            )
        return "Nenhum preview disponível"
    preview_template.short_description = 'Preview'
    
    def ativar_templates(self, request, queryset):
        updated = queryset.update(ativo=True)
        self.message_user(request, f"{updated} template(s) ativado(s).")
    ativar_templates.short_description = 'Ativar selecionados'
    
    def inativar_templates(self, request, queryset):
        updated = queryset.update(ativo=False)
        self.message_user(request, f"{updated} template(s) inativado(s).")
    inativar_templates.short_description = 'Inativar selecionados'


# ============================================================================
# ADMIN CUSTOMIZADO PARA USER COM TELEFONE
# ============================================================================

class UserAdmin(BaseUserAdmin):
    """Admin customizado para User com campo telefone"""
    
    # Adicionar telefone aos campos de edição
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informações de Contato', {
            'fields': ('telefone',)
        }),
    )
    
    # Adicionar telefone aos campos de criação
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Informações de Contato', {
            'fields': ('telefone',)
        }),
    )
    
    # Adicionar telefone à lista de exibição
    list_display = BaseUserAdmin.list_display + ('telefone',)
    
    # Adicionar telefone aos campos de busca
    search_fields = BaseUserAdmin.search_fields + ('telefone',)
    
    def telefone_formatado(self, obj):
        """Exibe telefone formatado"""
        if obj.telefone:
            # Remove caracteres não numéricos e formata
            numeros = ''.join(filter(str.isdigit, obj.telefone))
            if len(numeros) >= 10:
                if len(numeros) == 11:
                    return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
                elif len(numeros) == 10:
                    return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
        return obj.telefone or '-'
    telefone_formatado.short_description = 'Telefone'


# Desregistrar o admin padrão do User e registrar o customizado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ============================================================================
# ADMIN - CAMPANHAS DE TRÁFEGO PAGO
# ============================================================================

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
        if not change:  # Se for criação
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
        # Se marcar como rejeitada manualmente
        if not obj.aceita and not obj.rejeitada_por:
            obj.rejeitada_por = request.user
            obj.data_rejeicao = timezone.now()
        super().save_model(request, obj, form, change)


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
