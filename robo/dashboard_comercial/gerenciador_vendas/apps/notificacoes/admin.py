from django.contrib import admin
from django.utils.html import format_html

from apps.notificacoes.models import (
    TipoNotificacao,
    CanalNotificacao,
    PreferenciaNotificacao,
    Notificacao,
    TemplateNotificacao,
)


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
