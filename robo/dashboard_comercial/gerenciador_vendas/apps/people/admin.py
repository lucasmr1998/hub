from django.contrib import admin

from apps.people.models import (
    Colaborador, ConfiguracaoPeople, HistoricoSituacao, Unidade,
)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'cidade', 'estado', 'ativo', 'tenant')
    list_filter = ('ativo', 'tenant', 'estado')
    search_fields = ('nome', 'codigo', 'cnpj')
    ordering = ('tenant', 'nome')

    def get_queryset(self, request):
        return Unidade.all_tenants.select_related('tenant', 'responsavel')


@admin.register(ConfiguracaoPeople)
class ConfiguracaoPeopleAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'dias_experiencia_padrao', 'exige_cpf_no_autocadastro',
                    'versao_consentimento_lgpd')
    list_filter = ('exige_cpf_no_autocadastro',)

    def get_queryset(self, request):
        return ConfiguracaoPeople.all_tenants.select_related('tenant')


class HistoricoSituacaoInline(admin.TabularInline):
    model = HistoricoSituacao
    extra = 0
    can_delete = False
    fields = ('criado_em', 'de', 'para', 'motivo', 'origem', 'usuario', 'dados')
    readonly_fields = fields
    ordering = ('-criado_em',)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    """
    Admin de apoio pra dev e suporte. Nao e a tela do produto.

    `situacao` e readonly de proposito. A guarda do model levanta
    TransicaoNaoAutorizada em qualquer save que mude a fase sem passar por
    mover_situacao(), entao um campo editavel aqui so entregaria um erro 500 a
    quem tentasse. A fase se muda pelo board, que valida a transicao e grava
    historico.
    """

    list_display = ('nome_completo', 'situacao', 'unidade', 'cargo', 'cpf',
                    'pendente_revisao', 'tenant')
    list_filter = ('situacao', 'pendente_revisao', 'cpf_valido', 'origem_cadastro',
                   'tenant', 'unidade')
    search_fields = ('nome_completo', 'cpf', 'telefone', 'email')
    ordering = ('tenant', 'nome_completo')
    inlines = [HistoricoSituacaoInline]

    readonly_fields = ('situacao', 'ponto_entrada', 'origem_cadastro', 'cpf_valido',
                       'prorrogacoes_experiencia', 'criado_em', 'atualizado_em',
                       'consentimento_lgpd', 'consentimento_lgpd_em',
                       'consentimento_lgpd_ip', 'consentimento_lgpd_versao',
                       'consentimento_lgpd_user_agent')

    fieldsets = (
        ('Ciclo de vida', {
            'fields': ('situacao', 'ponto_entrada', 'unidade', 'pendente_revisao'),
            'description': 'A fase so muda pelo board, que valida a transicao e '
                           'grava historico. Por isso ela aparece aqui somente pra leitura.',
        }),
        ('Identificacao', {
            'fields': ('nome_completo', 'primeiro_nome', 'cpf', 'cpf_valido',
                       'rg', 'pis', 'data_nascimento'),
        }),
        ('Contato', {
            'fields': ('telefone', 'email'),
        }),
        ('Endereco', {
            'classes': ('collapse',),
            'fields': ('cep', 'rua', 'numero', 'complemento', 'bairro', 'cidade', 'estado'),
        }),
        ('Pagamento', {
            'classes': ('collapse',),
            'fields': ('tipo_chave_pix', 'chave_pix'),
        }),
        ('Vinculo', {
            'fields': ('cargo', 'regime_contratacao', 'data_admissao',
                       'data_fim_experiencia', 'prorrogacoes_experiencia',
                       'data_desligamento', 'motivo_desligamento',
                       'elegivel_recontratacao'),
        }),
        ('LGPD', {
            'classes': ('collapse',),
            'fields': ('consentimento_lgpd', 'consentimento_lgpd_em',
                       'consentimento_lgpd_ip', 'consentimento_lgpd_versao',
                       'consentimento_lgpd_user_agent'),
        }),
        ('Auditoria', {
            'classes': ('collapse',),
            'fields': ('origem_cadastro', 'criado_por', 'observacoes',
                       'criado_em', 'atualizado_em'),
        }),
    )

    def get_queryset(self, request):
        return Colaborador.all_tenants.select_related('tenant', 'unidade')

    def has_delete_permission(self, request, obj=None):
        """Colaborador nao se apaga, se desliga. O model levantaria de qualquer
        jeito; melhor nao oferecer o botao."""
        return False


@admin.register(HistoricoSituacao)
class HistoricoSituacaoAdmin(admin.ModelAdmin):
    list_display = ('criado_em', 'colaborador', 'de', 'para', 'motivo', 'origem', 'usuario')
    list_filter = ('para', 'origem', 'tenant')
    search_fields = ('colaborador__nome_completo', 'motivo')
    ordering = ('-criado_em',)

    def get_queryset(self, request):
        return HistoricoSituacao.all_tenants.select_related(
            'tenant', 'colaborador', 'usuario')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        """Trilha de auditoria nao se edita."""
        return False
