from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils import timezone

from apps.sistema.models import (
    ConfiguracaoEmpresa,
    ConfiguracaoSistema,
    LogSistema,
    StatusConfiguravel,
)


class AdminSiteCustom(admin.AdminSite):
    site_header = 'Megalink - Painel Comercial'
    site_title = 'Megalink'
    index_title = 'Painel de Controle'

    def index(self, request, extra_context=None):
        """
        Pagina principal personalizada do admin
        """
        extra_context = extra_context or {}

        try:
            from apps.comercial.leads.models import LeadProspecto
            from apps.comercial.atendimento.models import AtendimentoFluxo
            from apps.comercial.cadastro.models import CadastroCliente, DocumentoLead

            total_leads = LeadProspecto.objects.count()
            leads_ativos = LeadProspecto.objects.filter(ativo=True).count()
            from apps.comercial.leads.models import Prospecto
            total_prospectos = Prospecto.objects.count()
            atendimentos_hoje = AtendimentoFluxo.objects.filter(
                data_inicio__date=timezone.now().date()
            ).count()

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
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao carregar estatisticas do admin: {e}")

        return super().index(request, extra_context)


# Criar instancia customizada do admin
admin_site = AdminSiteCustom(name='admin')

# Configurar o site padrao tambem
admin.site.site_header = AdminSiteCustom.site_header
admin.site.site_title = AdminSiteCustom.site_title
admin.site.index_title = AdminSiteCustom.index_title


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
# ADMIN CUSTOMIZADO PARA USER COM TELEFONE
# ============================================================================

class UserAdmin(BaseUserAdmin):
    """Admin customizado para User — telefone migrado para PerfilUsuario"""
    pass


# Desregistrar o admin padrao do User e registrar o customizado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
