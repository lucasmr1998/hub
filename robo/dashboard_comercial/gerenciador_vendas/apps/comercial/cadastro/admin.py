from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from apps.comercial.cadastro.models import (
    ConfiguracaoCadastro,
    PlanoInternet,
    OpcaoVencimento,
    CadastroCliente,
    DocumentoLead,
)


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
        """Acao para finalizar cadastros selecionados"""
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
        """Acao para gerar leads para cadastros selecionados"""
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
        """Retorna informacoes formatadas do lead"""
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
        """Acao para aprovar documentos selecionados"""
        count = 0
        for doc in queryset.filter(status__in=['pendente', 'em_analise']):
            doc.validar_documento(
                status='aprovado',
                observacoes='Aprovado via admin',
                usuario=request.user.username if request.user.is_authenticated else 'admin'
            )
            count += 1

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
        """Acao para rejeitar documentos selecionados"""
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
