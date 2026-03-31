from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft


# =========================================================================
# IntegracaoAPI
# =========================================================================

class IntegracaoAPIForm(forms.ModelForm):
    """Form customizado que exibe password e client_secret como campos de senha."""

    password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        label="Senha",
        help_text="Deixe em branco para manter a senha atual.",
    )
    client_secret = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        label="Client Secret",
        help_text="Deixe em branco para manter o secret atual.",
    )

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password and self.instance.pk:
            return self.instance.password
        return password

    def clean_client_secret(self):
        client_secret = self.cleaned_data.get('client_secret')
        if not client_secret and self.instance.pk:
            return self.instance.client_secret
        return client_secret

    class Meta:
        model = IntegracaoAPI
        fields = '__all__'


@admin.register(IntegracaoAPI)
class IntegracaoAPIAdmin(admin.ModelAdmin):
    form = IntegracaoAPIForm

    list_display = [
        'nome', 'tipo', 'base_url', 'ativa', 'token_status', 'data_atualizacao',
    ]
    list_filter = ['tipo', 'ativa']
    search_fields = ['nome', 'base_url']
    readonly_fields = ['access_token', 'token_expira_em', 'data_criacao', 'data_atualizacao']

    fieldsets = (
        ('Identificação', {
            'fields': ('nome', 'tipo', 'base_url', 'ativa'),
        }),
        ('Credenciais OAuth', {
            'fields': ('client_id', 'client_secret', 'username', 'password', 'grant_type'),
        }),
        ('Token (automático)', {
            'classes': ('collapse',),
            'fields': ('access_token', 'token_expira_em'),
        }),
        ('Configurações Extras', {
            'classes': ('collapse',),
            'fields': ('configuracoes_extras',),
        }),
        ('Auditoria', {
            'classes': ('collapse',),
            'fields': ('data_criacao', 'data_atualizacao'),
        }),
    )

    @admin.display(description="Token", boolean=True)
    def token_status(self, obj):
        return obj.token_valido


# =========================================================================
# LogIntegracao
# =========================================================================

@admin.register(LogIntegracao)
class LogIntegracaoAdmin(admin.ModelAdmin):
    list_display = [
        'data_criacao', 'integracao', 'metodo', 'endpoint',
        'status_code', 'sucesso_badge', 'tempo_resposta_ms', 'lead_link',
    ]
    list_filter = ['sucesso', 'metodo', 'integracao', 'status_code']
    search_fields = ['endpoint', 'mensagem_erro']
    readonly_fields = [
        'integracao', 'lead', 'endpoint', 'metodo',
        'payload_enviado', 'resposta_recebida', 'status_code',
        'sucesso', 'mensagem_erro', 'tempo_resposta_ms', 'data_criacao',
    ]
    date_hierarchy = 'data_criacao'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Sucesso")
    def sucesso_badge(self, obj):
        if obj.sucesso:
            return format_html(
                '<span style="color:#27ae60;font-weight:bold;">&#10004; OK</span>'
            )
        return format_html(
            '<span style="color:#e74c3c;font-weight:bold;">&#10008; ERRO</span>'
        )

    @admin.display(description="Lead")
    def lead_link(self, obj):
        if obj.lead:
            from django.urls import reverse
            url = reverse('admin:leads_leadprospecto_change', args=[obj.lead.pk])
            return format_html('<a href="{}">{}</a>', url, obj.lead.nome_razaosocial)
        return '-'


# =========================================================================
# ServicoClienteHubsoft (inline)
# =========================================================================

class ServicoClienteHubsoftInline(admin.TabularInline):
    model = ServicoClienteHubsoft
    extra = 0
    show_change_link = True
    fields = [
        'id_cliente_servico', 'nome', 'valor', 'status',
        'velocidade_download', 'login', 'data_venda',
        'vendedor_nome', 'data_sync',
    ]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# =========================================================================
# ClienteHubsoft
# =========================================================================

@admin.register(ClienteHubsoft)
class ClienteHubsoftAdmin(admin.ModelAdmin):
    list_display = [
        'nome_razaosocial', 'cpf_cnpj', 'id_cliente', 'codigo_cliente',
        'telefone_primario', 'email_principal', 'ativo_badge',
        'qtd_servicos', 'houve_alteracao_badge', 'data_sync',
    ]
    list_filter = ['ativo', 'tipo_pessoa', 'houve_alteracao', 'origem_cliente']
    search_fields = ['nome_razaosocial', 'cpf_cnpj', 'email_principal', 'telefone_primario']
    readonly_fields = [
        'id_cliente', 'uuid_cliente', 'codigo_cliente',
        'nome_razaosocial', 'nome_fantasia', 'tipo_pessoa', 'cpf_cnpj',
        'telefone_primario', 'telefone_secundario', 'telefone_terciario',
        'email_principal', 'email_secundario',
        'rg', 'rg_emissao', 'inscricao_municipal', 'inscricao_estadual',
        'data_cadastro_hubsoft', 'data_nascimento',
        'nome_pai', 'nome_mae', 'estado_civil', 'genero', 'nacionalidade', 'profissao',
        'alerta', 'alerta_mensagens', 'ativo',
        'id_origem_cliente', 'origem_cliente', 'motivo_contratacao', 'id_externo',
        'grupos', 'dados_completos',
        'data_atualizacao_hubsoft', 'data_sync', 'data_criacao',
        'houve_alteracao', 'historico_alteracoes',
        'lead_link',
    ]
    date_hierarchy = 'data_sync'
    inlines = [ServicoClienteHubsoftInline]

    fieldsets = (
        ('Identificação Hubsoft', {
            'fields': (
                'id_cliente', 'uuid_cliente', 'codigo_cliente',
                'lead_link', 'ativo',
            ),
        }),
        ('Dados Pessoais', {
            'fields': (
                'nome_razaosocial', 'nome_fantasia', 'tipo_pessoa', 'cpf_cnpj',
                'data_nascimento', 'rg', 'rg_emissao',
                'genero', 'estado_civil', 'nacionalidade', 'profissao',
                'nome_pai', 'nome_mae',
            ),
        }),
        ('Contato', {
            'fields': (
                'telefone_primario', 'telefone_secundario', 'telefone_terciario',
                'email_principal', 'email_secundario',
            ),
        }),
        ('Origem e Classificação', {
            'fields': (
                'id_origem_cliente', 'origem_cliente',
                'motivo_contratacao', 'id_externo', 'grupos',
            ),
        }),
        ('Alertas', {
            'classes': ('collapse',),
            'fields': ('alerta', 'alerta_mensagens'),
        }),
        ('PJ (Inscrições)', {
            'classes': ('collapse',),
            'fields': ('inscricao_municipal', 'inscricao_estadual'),
        }),
        ('Sincronização', {
            'fields': (
                'data_cadastro_hubsoft', 'data_atualizacao_hubsoft',
                'data_sync', 'data_criacao',
                'houve_alteracao', 'historico_alteracoes',
            ),
        }),
        ('JSON Bruto', {
            'classes': ('collapse',),
            'fields': ('dados_completos',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Ativo", boolean=True)
    def ativo_badge(self, obj):
        return obj.ativo

    @admin.display(description="Alterado", boolean=True)
    def houve_alteracao_badge(self, obj):
        return obj.houve_alteracao

    @admin.display(description="Serviços")
    def qtd_servicos(self, obj):
        return obj.servicos.count()

    @admin.display(description="Lead")
    def lead_link(self, obj):
        if obj.lead:
            from django.urls import reverse
            url = reverse('admin:leads_leadprospecto_change', args=[obj.lead.pk])
            return format_html('<a href="{}">{}</a>', url, obj.lead.nome_razaosocial)
        return '-'


# =========================================================================
# ServicoClienteHubsoft (standalone)
# =========================================================================

@admin.register(ServicoClienteHubsoft)
class ServicoClienteHubsoftAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'cliente_nome', 'status', 'valor',
        'velocidade_download', 'login',
        'vendedor_nome', 'data_sync',
    ]
    list_filter = ['status_prefixo', 'tecnologia']
    search_fields = ['nome', 'login', 'cliente__nome_razaosocial', 'cliente__cpf_cnpj']
    readonly_fields = [
        'cliente', 'id_cliente_servico', 'uuid_cliente_servico', 'id_servico',
        'numero_plano', 'nome', 'valor', 'tecnologia',
        'velocidade_download', 'velocidade_upload',
        'status', 'status_prefixo',
        'data_habilitacao', 'data_venda', 'data_inicio_contrato',
        'data_fim_contrato', 'vigencia_meses', 'data_cadastro_servico',
        'data_atualizacao_servico',
        'id_cliente_servico_autenticacao', 'login', 'senha',
        'mac_addr', 'phy_addr', 'vlan', 'ipv4', 'ipv6',
        'id_motivo_cancelamento', 'data_cancelamento', 'motivo_cancelamento',
        'id_vendedor', 'vendedor_nome', 'vendedor_email',
        'dados_completos', 'data_sync',
    ]

    fieldsets = (
        ('Plano', {
            'fields': (
                'cliente', 'id_cliente_servico', 'uuid_cliente_servico',
                'id_servico', 'numero_plano', 'nome', 'valor',
                'tecnologia', 'velocidade_download', 'velocidade_upload',
            ),
        }),
        ('Status', {
            'fields': ('status', 'status_prefixo'),
        }),
        ('Datas / Contrato', {
            'fields': (
                'data_habilitacao', 'data_venda',
                'data_inicio_contrato', 'data_fim_contrato', 'vigencia_meses',
                'data_cadastro_servico', 'data_atualizacao_servico',
            ),
        }),
        ('Autenticação PPPoE', {
            'fields': (
                'id_cliente_servico_autenticacao', 'login', 'senha',
                'mac_addr', 'phy_addr', 'vlan', 'ipv4', 'ipv6',
            ),
        }),
        ('Cancelamento', {
            'classes': ('collapse',),
            'fields': ('id_motivo_cancelamento', 'data_cancelamento', 'motivo_cancelamento'),
        }),
        ('Vendedor', {
            'fields': ('id_vendedor', 'vendedor_nome', 'vendedor_email'),
        }),
        ('JSON Bruto', {
            'classes': ('collapse',),
            'fields': ('dados_completos',),
        }),
        ('Sincronização', {
            'fields': ('data_sync',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Cliente")
    def cliente_nome(self, obj):
        return obj.cliente.nome_razaosocial
