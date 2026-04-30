from django.db import models
from django.core.validators import RegexValidator
from django.contrib.auth.models import User
from django.utils import timezone
from apps.sistema.managers import TenantManager
from apps.sistema.validators import tenant_upload_path


# ============================================================================
# PLANOS — define o que cada plano oferece
# ============================================================================

class Plano(models.Model):
    """
    Define os planos vendidos pela Hubtrix.
    Cada plano pertence a um módulo e libera features específicas.
    """
    MODULO_CHOICES = [
        ('comercial', 'Comercial'),
        ('marketing', 'Marketing'),
        ('cs', 'CS'),
        ('workspace', 'Workspace'),
    ]
    TIER_CHOICES = [
        ('starter', 'Starter'),
        ('start', 'Start'),
        ('pro', 'Pro'),
    ]

    nome = models.CharField(max_length=100, verbose_name="Nome do Plano")
    modulo = models.CharField(max_length=20, choices=MODULO_CHOICES, verbose_name="Módulo")
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, verbose_name="Tier")
    descricao = models.TextField(blank=True, verbose_name="Descrição")

    # Preço
    preco_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Mensalidade (R$)")
    preco_transacional = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valor Transacional (R$)")
    unidade_transacional = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Unidade Transacional",
        help_text="Ex: por venda, por contato/mês, por cliente ativo"
    )

    # Ordem de exibição
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    destaque = models.BooleanField(default=False, verbose_name="Plano destaque", help_text="Destaca na página de preços")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_plano'
        verbose_name = "Plano"
        verbose_name_plural = "Planos"
        ordering = ['modulo', 'ordem']
        unique_together = [['modulo', 'tier']]

    def __str__(self):
        return f"{self.nome} ({self.get_modulo_display()} {self.get_tier_display()})"


class FeaturePlano(models.Model):
    """
    Features individuais que cada plano libera.
    Permite controlar granularmente o que está disponível.
    """
    CATEGORIA_CHOICES = [
        ('core', 'Core'),
        ('crm', 'CRM'),
        ('automacao', 'Automação'),
        ('relatorios', 'Relatórios'),
        ('integracao', 'Integração'),
        ('suporte', 'Suporte'),
    ]

    plano = models.ForeignKey(Plano, on_delete=models.CASCADE, related_name='features', verbose_name="Plano")
    nome = models.CharField(max_length=200, verbose_name="Feature")
    slug = models.SlugField(verbose_name="Slug", help_text="Identificador usado no código para verificar acesso")
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='core', verbose_name="Categoria")
    descricao = models.CharField(max_length=500, blank=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_feature_plano'
        verbose_name = "Feature do Plano"
        verbose_name_plural = "Features dos Planos"
        ordering = ['plano', 'categoria', 'nome']

    def __str__(self):
        return f"{self.plano.nome} — {self.nome}"


# ============================================================================
# TENANT — base do multi-tenancy
# ============================================================================

class Tenant(models.Model):
    """
    Cada tenant é um provedor de internet cliente da Hubtrix.
    Todos os models de domínio herdam TenantMixin e recebem FK para cá.
    """
    PLANO_CHOICES = [
        ('starter', 'Starter'),
        ('start', 'Start'),
        ('pro', 'Pro'),
    ]

    nome = models.CharField(max_length=200, verbose_name="Nome do Provedor")
    cnpj = models.CharField(max_length=18, unique=True, blank=True, null=True, verbose_name="CNPJ")
    slug = models.SlugField(unique=True, verbose_name="Slug")

    # Módulos contratados
    modulo_comercial = models.BooleanField(default=True, verbose_name="Comercial ativo")
    modulo_marketing = models.BooleanField(default=False, verbose_name="Marketing ativo")
    modulo_cs = models.BooleanField(default=False, verbose_name="CS ativo")
    modulo_workspace = models.BooleanField(default=False, verbose_name="Workspace ativo")

    # Plano por módulo (string para compatibilidade, FK para features)
    plano_comercial = models.CharField(max_length=10, choices=PLANO_CHOICES, default='starter', verbose_name="Plano Comercial")
    plano_marketing = models.CharField(max_length=10, choices=PLANO_CHOICES, default='starter', verbose_name="Plano Marketing")
    plano_cs = models.CharField(max_length=10, choices=PLANO_CHOICES, default='starter', verbose_name="Plano CS")
    plano_workspace = models.CharField(max_length=10, choices=PLANO_CHOICES, default='starter', verbose_name="Plano Workspace")

    # FK para os planos (permite verificar features)
    plano_comercial_ref = models.ForeignKey(
        Plano, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tenants_comercial', verbose_name="Plano Comercial (ref)",
        limit_choices_to={'modulo': 'comercial', 'ativo': True},
    )
    plano_marketing_ref = models.ForeignKey(
        Plano, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tenants_marketing', verbose_name="Plano Marketing (ref)",
        limit_choices_to={'modulo': 'marketing', 'ativo': True},
    )
    plano_cs_ref = models.ForeignKey(
        Plano, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tenants_cs', verbose_name="Plano CS (ref)",
        limit_choices_to={'modulo': 'cs', 'ativo': True},
    )
    plano_workspace_ref = models.ForeignKey(
        Plano, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tenants_workspace', verbose_name="Plano Workspace (ref)",
        limit_choices_to={'modulo': 'workspace', 'ativo': True},
    )

    # HubSoft
    hubsoft_url = models.URLField(blank=True, null=True, verbose_name="URL HubSoft")
    hubsoft_token = models.CharField(max_length=255, blank=True, null=True, verbose_name="Token HubSoft")

    # Trial
    em_trial = models.BooleanField(default=False, verbose_name="Em trial")
    trial_inicio = models.DateField(blank=True, null=True, verbose_name="Início do trial")
    trial_fim = models.DateField(blank=True, null=True, verbose_name="Fim do trial")

    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_tenant'
        verbose_name = "Tenant (Provedor)"
        verbose_name_plural = "Tenants (Provedores)"
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def tem_modulo(self, modulo):
        return getattr(self, f'modulo_{modulo}', False)

    def plano_do_modulo(self, modulo):
        return getattr(self, f'plano_{modulo}', 'starter')

    def plano_ref(self, modulo):
        """Retorna o objeto Plano do módulo (ou None)."""
        return getattr(self, f'plano_{modulo}_ref', None)

    def tem_feature(self, slug_feature):
        """Verifica se o tenant tem acesso a uma feature pelo slug."""
        for modulo in ['comercial', 'marketing', 'cs', 'workspace']:
            plano = self.plano_ref(modulo)
            if plano and plano.features.filter(slug=slug_feature, ativo=True).exists():
                return True
        return False

    def features_ativas(self):
        """Retorna todos os slugs de features ativas do tenant."""
        slugs = set()
        for modulo in ['comercial', 'marketing', 'cs', 'workspace']:
            plano = self.plano_ref(modulo)
            if plano:
                slugs.update(plano.features.filter(ativo=True).values_list('slug', flat=True))
        return slugs


# ============================================================================
# PERFIL DE USUARIO — substitui o monkey-patch User.add_to_class
# ============================================================================

class PerfilUsuario(models.Model):
    """
    Extende o User do Django com tenant e dados extras.
    Substitui User.add_to_class('telefone', ...) que existia em vendas_web.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='perfil', verbose_name="Usuário"
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='usuarios', verbose_name="Tenant"
    )
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    senha_temporaria = models.BooleanField(
        default=False, verbose_name="Senha temporária",
        help_text="Se True, o usuário será forçado a trocar a senha no próximo login"
    )

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_perfil_usuario'
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuário"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.tenant.nome})"


# ============================================================================
# PERMISSÕES — controle granular por módulo + funcionalidade
# ============================================================================

class Funcionalidade(models.Model):
    """
    Funcionalidade individual do sistema (ex: 'ver_pipeline', 'criar_tarefa').
    Seed fixo, não editável pelo tenant.
    """
    MODULO_CHOICES = [
        ('comercial', 'Comercial'),
        ('marketing', 'Marketing'),
        ('cs', 'Customer Success'),
        ('inbox', 'Inbox / Suporte'),
        ('configuracoes', 'Configurações'),
        ('workspace', 'Workspace'),
    ]

    modulo = models.CharField(max_length=20, choices=MODULO_CHOICES, verbose_name="Módulo")
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código",
        help_text="Identificador único (ex: comercial.ver_pipeline)")
    nome = models.CharField(max_length=100, verbose_name="Nome",
        help_text="Nome amigável (ex: Ver Pipeline)")
    descricao = models.CharField(max_length=255, blank=True, verbose_name="Descrição")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem de exibição")

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_funcionalidade'
        verbose_name = "Funcionalidade"
        verbose_name_plural = "Funcionalidades"
        ordering = ['modulo', 'ordem']

    def __str__(self):
        return f"[{self.modulo}] {self.nome}"


class PerfilPermissao(models.Model):
    """
    Perfil de permissão reutilizável.
    Define quais funcionalidades estão liberadas.
    Atribuído a múltiplos usuários.
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='perfis_permissao', verbose_name="Tenant",
    )
    nome = models.CharField(max_length=100, verbose_name="Nome do Perfil",
        help_text="Ex: Vendedor, Supervisor Comercial, Agente Suporte")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    funcionalidades = models.ManyToManyField(
        Funcionalidade, blank=True,
        related_name='perfis', verbose_name="Funcionalidades",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_perfil_permissao'
        verbose_name = "Perfil de Permissão"
        verbose_name_plural = "Perfis de Permissão"
        unique_together = [['tenant', 'nome']]
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def total_usuarios(self):
        return self.usuarios.count()

    def tem_funcionalidade(self, codigo):
        """Verifica se o perfil tem uma funcionalidade específica."""
        return self.funcionalidades.filter(codigo=codigo).exists()

    def funcionalidades_por_modulo(self):
        """Retorna dict {modulo: [lista de codigos]}."""
        result = {}
        for f in self.funcionalidades.all():
            result.setdefault(f.modulo, []).append(f.codigo)
        return result


class PermissaoUsuario(models.Model):
    """
    Vincula um usuário a um PerfilPermissao.
    As permissões efetivas vêm do perfil.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='permissoes', verbose_name="Usuário",
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='permissoes_usuarios', verbose_name="Tenant",
    )
    perfil = models.ForeignKey(
        PerfilPermissao, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='usuarios', verbose_name="Perfil de Permissão",
    )

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_permissao_usuario'
        verbose_name = "Permissão de Usuário"
        verbose_name_plural = "Permissões de Usuários"

    def __str__(self):
        return f"{self.user.username} → {self.perfil.nome if self.perfil else 'Sem perfil'}"

    # ── Verificação de permissões ──

    def tem(self, codigo):
        """Verifica se o usuário tem uma funcionalidade. Ex: perm.tem('comercial.ver_pipeline')"""
        if not self.perfil:
            return False
        return self.perfil.tem_funcionalidade(codigo)

    @property
    def acesso_comercial(self):
        if not self.perfil:
            return False
        return self.perfil.funcionalidades.filter(modulo='comercial').exists()

    @property
    def acesso_marketing(self):
        if not self.perfil:
            return False
        return self.perfil.funcionalidades.filter(modulo='marketing').exists()

    @property
    def acesso_cs(self):
        if not self.perfil:
            return False
        return self.perfil.funcionalidades.filter(modulo='cs').exists()

    @property
    def acesso_inbox(self):
        if not self.perfil:
            return False
        return self.perfil.funcionalidades.filter(modulo='inbox').exists()

    @property
    def acesso_configuracoes(self):
        if not self.perfil:
            return False
        return self.perfil.funcionalidades.filter(modulo='configuracoes').exists()

    @property
    def acesso_workspace(self):
        if not self.perfil:
            return False
        return self.perfil.funcionalidades.filter(modulo='workspace').exists()

    @property
    def papel_comercial(self):
        if not self.perfil:
            return 'vendedor'
        if self.tem('comercial.configurar_pipeline'):
            return 'gerente'
        if self.tem('comercial.ver_todas_oportunidades'):
            return 'supervisor'
        return 'vendedor'

    @property
    def papel_inbox(self):
        if not self.perfil:
            return 'agente'
        if self.tem('inbox.configurar'):
            return 'gerente'
        if self.tem('inbox.ver_equipe'):
            return 'supervisor'
        return 'agente'

    def escopo_comercial(self):
        return {'vendedor': 'meus', 'supervisor': 'equipe', 'gerente': 'todos'}.get(self.papel_comercial, 'meus')

    def escopo_inbox(self):
        return {'agente': 'meus', 'supervisor': 'equipe', 'gerente': 'todos'}.get(self.papel_inbox, 'meus')

    def pode_configurar(self, modulo):
        if self.acesso_configuracoes:
            return True
        return self.tem(f'{modulo}.configurar') or self.tem(f'{modulo}.configurar_pipeline')

    @staticmethod
    def get_for_user(user):
        if user.is_superuser:
            return None
        try:
            return user.permissoes
        except PermissaoUsuario.DoesNotExist:
            return None


# ============================================================================
# CONFIGURACOES — migradas de vendas_web
# ============================================================================

class ConfiguracaoEmpresa(models.Model):
    """
    Configuração visual da empresa (nome, logo, cores).
    Migrado de vendas_web — db_table mantida para compatibilidade.
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='configuracoes_empresa',
        verbose_name="Tenant",
        null=True, blank=True,
    )

    nome_empresa = models.CharField(max_length=100, verbose_name="Nome da Empresa", default="Provedor")
    logo_empresa = models.ImageField(upload_to=tenant_upload_path, verbose_name="Logo da Empresa", blank=True, null=True)
    cor_primaria = models.CharField(
        max_length=7, verbose_name="Cor Primária", default="#1F3D59",
        validators=[RegexValidator(regex='^#[0-9A-Fa-f]{6}$', message='Formato inválido. Use #RRGGBB')]
    )
    cor_secundaria = models.CharField(
        max_length=7, verbose_name="Cor Secundária", default="#2c5aa0",
        validators=[RegexValidator(regex='^#[0-9A-Fa-f]{6}$', message='Formato inválido. Use #RRGGBB')]
    )
    # Integracoes de leads
    enviar_leads_integracao = models.BooleanField(
        default=False, verbose_name="Enviar leads para integração",
        help_text="Envia leads automaticamente para a integração selecionada ao cadastrar"
    )
    integracao_leads = models.ForeignKey(
        'integracoes.IntegracaoAPI', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='config_empresa_leads',
        verbose_name="Integração para leads",
        help_text="Integração que recebe os leads (ex: HubSoft)"
    )

    ativo = models.BooleanField(default=True, verbose_name="Configuração Ativa")
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = 'vendas_web_configuracaoempresa'
        verbose_name = "Configuração da Empresa"
        verbose_name_plural = "Configurações da Empresa"
        ordering = ['-ativo', '-data_criacao']

    def __str__(self):
        return f"{self.nome_empresa} ({'Ativo' if self.ativo else 'Inativo'})"

    def save(self, *args, **kwargs):
        if self.ativo:
            qs = ConfiguracaoEmpresa.objects.filter(ativo=True)
            if self.tenant_id:
                qs = qs.filter(tenant=self.tenant)
            qs.exclude(id=self.id).update(ativo=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_configuracao_ativa(cls, tenant=None):
        qs = cls.objects.filter(ativo=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.first()


class ConfiguracaoSistema(models.Model):
    """
    Configurações gerais do sistema (chave-valor).
    Migrado de vendas_web.
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='configuracoes_sistema',
        verbose_name="Tenant",
        null=True, blank=True,
    )

    chave = models.CharField(max_length=100, verbose_name="Chave")
    valor = models.TextField(verbose_name="Valor")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    tipo = models.CharField(
        max_length=20,
        choices=[('string', 'String'), ('integer', 'Integer'), ('boolean', 'Boolean'), ('json', 'JSON'), ('decimal', 'Decimal')],
        default='string', verbose_name="Tipo"
    )
    data_criacao = models.DateTimeField(default=timezone.now, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = 'configuracao_sistema'
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"
        ordering = ['chave']
        unique_together = [['tenant', 'chave']]

    def __str__(self):
        return f"{self.chave}: {self.valor[:50]}"


class ConfiguracaoRecontato(models.Model):
    """
    Configuração de recontato automático.
    Migrado de vendas_web.
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='configuracoes_recontato',
        verbose_name="Tenant",
        null=True, blank=True,
    )

    mensagem = models.TextField(verbose_name="Mensagem de Recontato")
    tempo_recontato = models.PositiveIntegerField(verbose_name="Tempo para Recontato")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = 'configuracoes_recontato'
        verbose_name = 'Configuração de Recontato'
        verbose_name_plural = "Configurações de Recontato"
        ordering = ['-ativo']

    def __str__(self):
        return f"{self.mensagem} - {self.tempo_recontato} - {self.ativo}"

    def get_tempo_recontato_formatado(self):
        if self.tempo_recontato:
            return f"{self.tempo_recontato} dias"
        return "N/A"


# ============================================================================
# STATUS E LOGS — migrados de vendas_web
# ============================================================================

class StatusConfiguravel(models.Model):
    """
    Tabela de status/labels configuráveis via admin.
    Migrado de vendas_web.
    """
    GRUPO_CHOICES = [
        ('lead_status_api', 'Lead: Status API'),
        ('prospecto_status', 'Prospecto: Status'),
        ('historico_status', 'Histórico: Status'),
        ('atendimento_status', 'Atendimento: Status'),
        ('fluxo_status', 'Fluxo: Status'),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='status_configuraveis',
        verbose_name="Tenant",
        null=True, blank=True,
    )

    grupo = models.CharField(max_length=50, choices=GRUPO_CHOICES, db_index=True)
    codigo = models.CharField(max_length=50, db_index=True)
    rotulo = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = 'status_configuravel'
        verbose_name = "Status Configurável"
        verbose_name_plural = "Status Configuráveis"
        unique_together = [('tenant', 'grupo', 'codigo')]
        ordering = ['grupo', 'ordem', 'codigo']

    def __str__(self):
        return f"{self.grupo}:{self.codigo} -> {self.rotulo}"

    @classmethod
    def get_label(cls, grupo, codigo, tenant=None):
        qs = cls.objects.filter(grupo=grupo, codigo=codigo, ativo=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        registro = qs.first()
        return registro.rotulo if registro else codigo


class LogSistema(models.Model):
    """
    Logs e auditoria do sistema.
    Migrado de vendas_web.
    """
    NIVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    CATEGORIA_CHOICES = [
        ('auth', 'Autenticacao'),
        ('leads', 'Leads'),
        ('crm', 'CRM'),
        ('inbox', 'Inbox'),
        ('suporte', 'Suporte'),
        ('cs', 'Customer Success'),
        ('marketing', 'Marketing'),
        ('config', 'Configuracoes'),
        ('admin', 'Admin Hubtrix'),
        ('integracao', 'Integracoes'),
        ('sistema', 'Sistema'),
        ('workspace', 'Workspace'),
    ]

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='logs',
        verbose_name="Tenant",
        null=True, blank=True,
    )

    nivel = models.CharField(max_length=10, choices=NIVEL_CHOICES, default='INFO', verbose_name="Nivel")
    modulo = models.CharField(max_length=100, verbose_name="Modulo")
    mensagem = models.TextField(verbose_name="Mensagem")
    dados_extras = models.JSONField(null=True, blank=True, verbose_name="Dados Extras")
    usuario = models.CharField(max_length=100, null=True, blank=True, verbose_name="Usuario")
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    data_criacao = models.DateTimeField(default=timezone.now, verbose_name="Data de Criacao")

    # Campos de classificacao (auditoria)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, blank=True, default='', verbose_name="Categoria", db_index=True)
    acao = models.CharField(max_length=50, blank=True, default='', verbose_name="Acao")
    entidade = models.CharField(max_length=50, blank=True, default='', verbose_name="Entidade")
    entidade_id = models.IntegerField(null=True, blank=True, verbose_name="ID da Entidade")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = 'log_sistema'
        verbose_name = "Log do Sistema"
        verbose_name_plural = "Logs do Sistema"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['nivel']),
            models.Index(fields=['data_criacao']),
            models.Index(fields=['modulo']),
            models.Index(fields=['categoria']),
            models.Index(fields=['categoria', 'acao']),
            models.Index(fields=['entidade', 'entidade_id']),
        ]

    def __str__(self):
        return f"{self.nivel} - {self.modulo} - {self.data_criacao.strftime('%d/%m/%Y %H:%M')}"


# ============================================================================
# RECUPERACAO DE SENHA
# ============================================================================

class ConfiguracaoRecuperacaoSenha(models.Model):
    """Configuracao global de recuperacao de senha (aurora-admin)."""
    # Email
    email_ativo = models.BooleanField(default=False, verbose_name="Recuperacao por Email")
    smtp_host = models.CharField(max_length=200, blank=True, default='', verbose_name="SMTP Host")
    smtp_porta = models.PositiveIntegerField(default=587, verbose_name="SMTP Porta")
    smtp_usuario = models.CharField(max_length=200, blank=True, default='', verbose_name="SMTP Usuario")
    smtp_senha = models.CharField(max_length=200, blank=True, default='', verbose_name="SMTP Senha")
    smtp_tls = models.BooleanField(default=True, verbose_name="Usar TLS")
    email_remetente = models.EmailField(blank=True, default='', verbose_name="Email Remetente")

    # WhatsApp
    whatsapp_ativo = models.BooleanField(default=False, verbose_name="Recuperacao por WhatsApp")
    whatsapp_integracao = models.ForeignKey(
        'integracoes.IntegracaoAPI', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Integracao WhatsApp (Uazapi)",
        help_text="Integracao usada para enviar codigo via WhatsApp"
    )

    # Config
    codigo_expiracao_minutos = models.PositiveIntegerField(default=5, verbose_name="Expiracao do codigo (min)")
    max_tentativas = models.PositiveIntegerField(default=3, verbose_name="Max tentativas por codigo")

    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_config_recuperacao_senha'
        verbose_name = "Config Recuperacao de Senha"
        verbose_name_plural = "Config Recuperacao de Senha"

    def __str__(self):
        metodos = []
        if self.email_ativo:
            metodos.append('Email')
        if self.whatsapp_ativo:
            metodos.append('WhatsApp')
        return f"Recuperacao: {', '.join(metodos) or 'Desativada'}"

    @classmethod
    def get_config(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj


class CodigoRecuperacaoSenha(models.Model):
    """Codigo temporario para recuperacao de senha."""
    METODO_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='codigos_recuperacao')
    codigo = models.CharField(max_length=6, verbose_name="Codigo")
    token = models.CharField(max_length=64, blank=True, default='', verbose_name="Token (para email)")
    metodo = models.CharField(max_length=10, choices=METODO_CHOICES, verbose_name="Metodo")
    tentativas = models.PositiveIntegerField(default=0, verbose_name="Tentativas")
    usado = models.BooleanField(default=False, verbose_name="Usado")
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField(verbose_name="Expira em")

    class Meta:
        app_label = 'sistema'
        db_table = 'sistema_codigo_recuperacao_senha'
        verbose_name = "Codigo de Recuperacao"
        verbose_name_plural = "Codigos de Recuperacao"
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.user.username} - {self.metodo} - {'Usado' if self.usado else 'Ativo'}"

    @property
    def expirado(self):
        return timezone.now() > self.expira_em

    @property
    def bloqueado(self):
        config = ConfiguracaoRecuperacaoSenha.get_config()
        return self.tentativas >= config.max_tentativas
