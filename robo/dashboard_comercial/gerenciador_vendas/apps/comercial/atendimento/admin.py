from django.contrib import admin
from django.utils.html import format_html
from django.db import models
from django import forms

from apps.comercial.atendimento.models import (
    FluxoAtendimento,
    QuestaoFluxo,
    AtendimentoFluxo,
    TentativaResposta,
    RespostaQuestao,
)


# ============================================================================
# INLINES PARA FLUXO DE ATENDIMENTO
# ============================================================================

class QuestaoFluxoInline(admin.TabularInline):
    """Inline para questoes dentro do fluxo"""
    model = QuestaoFluxo
    fields = ('indice', 'titulo', 'tipo_questao', 'tipo_validacao', 'ativo')
    extra = 1
    show_change_link = True
    ordering = ['indice']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('questao_dependencia')

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        if obj:
            ultimo_indice = obj.questoes.aggregate(
                models.Max('indice')
            )['indice__max'] or 0

            if 'indice' in formset.form.base_fields:
                formset.form.base_fields['indice'].initial = ultimo_indice + 1
            if 'fluxo' in formset.form.base_fields:
                formset.form.base_fields['fluxo'].initial = obj
                formset.form.base_fields['fluxo'].widget = forms.HiddenInput()

        return formset

    def save_new_instance(self, request, instance, form, commit=True):
        if not instance.indice and instance.fluxo:
            ultimo_indice = instance.fluxo.questoes.aggregate(
                models.Max('indice')
            )['indice__max'] or 0
            instance.indice = ultimo_indice + 1

        return super().save_new_instance(request, instance, form, commit)


class AtendimentoFluxoInlineFluxo(admin.TabularInline):
    """Inline para atendimentos dentro do fluxo"""
    model = AtendimentoFluxo
    fields = ('lead', 'status', 'questao_atual', 'questoes_respondidas', 'data_inicio')
    readonly_fields = ('data_inicio',)
    extra = 0
    show_change_link = True
    ordering = ['-data_inicio']


# ============================================================================
# INLINES PARA QUESTAO
# ============================================================================

class RespostaQuestaoInline(admin.TabularInline):
    """Inline para respostas dentro da questao"""
    model = RespostaQuestao
    fields = ('atendimento', 'resposta', 'valida', 'data_resposta')
    readonly_fields = ('data_resposta',)
    extra = 0
    show_change_link = True
    ordering = ['-data_resposta']


class TentativaRespostaInlineQuestao(admin.TabularInline):
    """Inline para tentativas de resposta dentro da questao"""
    model = TentativaResposta
    fields = ('atendimento', 'tentativa_numero', 'valida', 'confianca_ia', 'estrategia_aplicada', 'data_tentativa')
    readonly_fields = ('data_tentativa',)
    extra = 0
    show_change_link = True
    ordering = ['-data_tentativa']
    verbose_name = "Tentativa"
    verbose_name_plural = "Tentativas"


# ============================================================================
# INLINES PARA ATENDIMENTO
# ============================================================================

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


# ============================================================================
# ADMIN CLASSES
# ============================================================================

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
    inlines = [QuestaoFluxoInline, AtendimentoFluxoInlineFluxo]
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

        add_questao_url = f"/admin/atendimento/questaofluxo/add/?fluxo={obj.id}"

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

    # Acoes em massa
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

        if not obj:
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

    # Acoes em massa
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
