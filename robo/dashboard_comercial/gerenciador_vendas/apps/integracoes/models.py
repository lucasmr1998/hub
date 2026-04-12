from django.db import models
from django.utils import timezone

from apps.sistema.encrypted_fields import EncryptedCharField, EncryptedTextField
from apps.sistema.mixins import TenantMixin


class IntegracaoAPI(TenantMixin):
    """
    Armazena credenciais e configuração de APIs externas.
    Cada registro representa uma conexão com um sistema (Hubsoft, etc).
    """
    TIPO_CHOICES = [
        ('hubsoft', 'HubSoft'),
        ('uazapi', 'Uazapi (WhatsApp)'),
        ('evolution', 'Evolution API (WhatsApp)'),
        ('meta_cloud', 'Meta Cloud API (WhatsApp)'),
        ('twilio_whatsapp', 'Twilio (WhatsApp)'),
        ('n8n', 'N8N (Automação)'),
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic (Claude)'),
        ('groq', 'Groq'),
        ('google_ai', 'Google AI (Gemini)'),
        ('outro', 'Outro'),
    ]

    # tenant FK herdado de TenantMixin

    api_token = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Token de API",
        help_text="Token unico para autenticar chamadas externas. Identifica o tenant automaticamente.",
        db_index=True,
    )

    nome = models.CharField(
        max_length=200,
        verbose_name="Nome da Integração",
        help_text="Ex: Hubsoft Megalink"
    )

    tipo = models.CharField(
        max_length=50,
        choices=TIPO_CHOICES,
        default='hubsoft',
        verbose_name="Tipo",
        db_index=True,
    )

    base_url = models.URLField(
        max_length=500,
        verbose_name="URL Base da API",
        help_text="Ex: https://api.megalinktelecom.hubsoft.com.br"
    )

    # --- Credenciais OAuth ------------------------------------------------
    client_id = models.CharField(
        max_length=200,
        verbose_name="Client ID",
    )

    client_secret = EncryptedCharField(
        max_length=500,
        verbose_name="Client Secret",
    )

    username = models.CharField(
        max_length=200,
        verbose_name="Usuário",
    )

    password = EncryptedCharField(
        max_length=200,
        verbose_name="Senha",
    )

    grant_type = models.CharField(
        max_length=50,
        default='password',
        verbose_name="Grant Type",
    )

    # --- Token cacheado ---------------------------------------------------
    access_token = EncryptedTextField(
        blank=True,
        default='',
        verbose_name="Access Token (cache)",
        help_text="Preenchido automaticamente ao autenticar"
    )

    token_expira_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Token Expira Em",
    )

    # --- Controle ---------------------------------------------------------
    ativa = models.BooleanField(
        default=True,
        verbose_name="Ativa",
        help_text="Desmarque para desabilitar esta integração"
    )

    configuracoes_extras = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configurações Extras",
        help_text="JSON com parâmetros adicionais (id_origem_cliente, id_vendedor padrão, etc.)"
    )

    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        db_table = 'integracoes_api'
        verbose_name = "Integração de API"
        verbose_name_plural = "🔗 01. Integrações de API"
        ordering = ['-ativa', 'nome']

    def __str__(self):
        status = "Ativa" if self.ativa else "Inativa"
        return f"{self.nome} ({self.get_tipo_display()}) — {status}"

    @property
    def token_valido(self):
        """Retorna True se o token cacheado ainda está válido."""
        if not self.access_token or not self.token_expira_em:
            return False
        return timezone.now() < self.token_expira_em

    # --- Modos de sincronização -------------------------------------------

    SYNC_MODOS = ['automatico', 'manual', 'desativado']

    SYNC_FEATURES = {
        'enviar_lead': 'Enviar lead ao criar',
        'sincronizar_cliente': 'Sincronizar dados do cliente',
        'sincronizar_servicos': 'Sincronizar servicos contratados',
    }

    def get_modo_sync(self, feature):
        """Retorna o modo de sync de uma feature: automatico|manual|desativado."""
        modos = self.configuracoes_extras.get('modos_sync', {})
        return modos.get(feature, 'automatico')

    def set_modo_sync(self, feature, modo):
        """Define o modo de sync de uma feature."""
        if modo not in self.SYNC_MODOS:
            return
        if 'modos_sync' not in self.configuracoes_extras:
            self.configuracoes_extras['modos_sync'] = {}
        self.configuracoes_extras['modos_sync'][feature] = modo
        self.save(update_fields=['configuracoes_extras'])

    def sync_habilitado(self, feature):
        """Retorna True se a feature está em modo automatico."""
        return self.get_modo_sync(feature) == 'automatico'

    def sync_permitido(self, feature):
        """Retorna True se a feature não está desativada (automatico ou manual)."""
        return self.get_modo_sync(feature) != 'desativado'

    @property
    def modos_sync_dict(self):
        """Retorna dict com todos os modos de sync."""
        modos = self.configuracoes_extras.get('modos_sync', {})
        return {f: modos.get(f, 'automatico') for f in self.SYNC_FEATURES}


class LogIntegracao(TenantMixin):
    """
    Registro de cada chamada feita a uma API externa, para auditoria e debug.
    """
    METODO_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ]

    integracao = models.ForeignKey(
        IntegracaoAPI,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name="Integração",
    )

    lead = models.ForeignKey(
        'leads.LeadProspecto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_integracao',
        verbose_name="Lead Relacionado",
    )

    endpoint = models.CharField(
        max_length=500,
        verbose_name="Endpoint",
        help_text="Ex: /api/v1/integracao/prospecto"
    )

    metodo = models.CharField(
        max_length=10,
        choices=METODO_CHOICES,
        default='POST',
        verbose_name="Método HTTP",
    )

    payload_enviado = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Payload Enviado",
    )

    resposta_recebida = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Resposta Recebida",
    )

    status_code = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Status Code HTTP",
    )

    sucesso = models.BooleanField(
        default=False,
        verbose_name="Sucesso",
    )

    mensagem_erro = models.TextField(
        blank=True,
        default='',
        verbose_name="Mensagem de Erro",
    )

    tempo_resposta_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo de Resposta (ms)",
    )

    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data",
    )

    class Meta:
        db_table = 'logs_integracao'
        verbose_name = "Log de Integração"
        verbose_name_plural = "📋 02. Logs de Integração"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['integracao', 'sucesso']),
            models.Index(fields=['lead']),
            models.Index(fields=['-data_criacao']),
            models.Index(fields=['status_code']),
        ]

    def __str__(self):
        status = "OK" if self.sucesso else "ERRO"
        return f"[{status}] {self.metodo} {self.endpoint} — {self.data_criacao:%d/%m/%Y %H:%M}"


class ClienteHubsoft(TenantMixin):
    """
    Espelho local do cliente retornado pela API GET /api/v1/integracao/cliente.
    Sincronizado periodicamente com o Hubsoft.
    """

    lead = models.ForeignKey(
        'leads.LeadProspecto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes_hubsoft',
        verbose_name="Lead de Origem",
    )

    # --- Identificação Hubsoft ------------------------------------------------
    id_cliente = models.IntegerField(unique=True, verbose_name="ID Cliente Hubsoft")
    uuid_cliente = models.CharField(max_length=100, blank=True, default='', verbose_name="UUID Cliente")
    codigo_cliente = models.IntegerField(null=True, blank=True, verbose_name="Código Cliente")

    # --- Dados pessoais -------------------------------------------------------
    nome_razaosocial = models.CharField(max_length=300, verbose_name="Nome / Razão Social")
    nome_fantasia = models.CharField(max_length=300, blank=True, default='', verbose_name="Nome Fantasia")
    tipo_pessoa = models.CharField(max_length=10, blank=True, default='pf', verbose_name="Tipo Pessoa")
    cpf_cnpj = models.CharField(max_length=20, db_index=True, verbose_name="CPF/CNPJ")

    telefone_primario = models.CharField(max_length=30, blank=True, default='', verbose_name="Telefone Primário")
    telefone_secundario = models.CharField(max_length=30, blank=True, default='', verbose_name="Telefone Secundário")
    telefone_terciario = models.CharField(max_length=30, blank=True, default='', verbose_name="Telefone Terciário")

    email_principal = models.CharField(max_length=254, blank=True, default='', verbose_name="E-mail Principal")
    email_secundario = models.CharField(max_length=254, blank=True, default='', verbose_name="E-mail Secundário")

    rg = models.CharField(max_length=30, blank=True, default='', verbose_name="RG")
    rg_emissao = models.CharField(max_length=30, blank=True, default='', verbose_name="RG Emissão")
    inscricao_municipal = models.CharField(max_length=50, blank=True, default='', verbose_name="Inscrição Municipal")
    inscricao_estadual = models.CharField(max_length=50, blank=True, default='', verbose_name="Inscrição Estadual")

    data_cadastro_hubsoft = models.DateTimeField(null=True, blank=True, verbose_name="Data Cadastro Hubsoft")
    data_nascimento = models.DateField(null=True, blank=True, verbose_name="Data Nascimento")

    nome_pai = models.CharField(max_length=300, blank=True, default='', verbose_name="Nome do Pai")
    nome_mae = models.CharField(max_length=300, blank=True, default='', verbose_name="Nome da Mãe")
    estado_civil = models.CharField(max_length=50, blank=True, default='', verbose_name="Estado Civil")
    genero = models.CharField(max_length=30, blank=True, default='', verbose_name="Gênero")
    nacionalidade = models.CharField(max_length=50, blank=True, default='', verbose_name="Nacionalidade")
    profissao = models.CharField(max_length=200, blank=True, default='', verbose_name="Profissão")

    # --- Alertas e status -----------------------------------------------------
    alerta = models.BooleanField(default=False, verbose_name="Alerta")
    alerta_mensagens = models.JSONField(default=list, blank=True, verbose_name="Mensagens de Alerta")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    # --- Origem e classificação -----------------------------------------------
    id_origem_cliente = models.IntegerField(null=True, blank=True, verbose_name="ID Origem Cliente")
    origem_cliente = models.CharField(max_length=200, blank=True, default='', verbose_name="Origem Cliente")
    motivo_contratacao = models.CharField(max_length=200, blank=True, default='', verbose_name="Motivo Contratação")
    id_externo = models.CharField(max_length=100, blank=True, default='', verbose_name="ID Externo")

    # --- Grupos ---------------------------------------------------------------
    grupos = models.JSONField(default=list, blank=True, verbose_name="Grupos")

    # --- Resposta completa (backup) -------------------------------------------
    dados_completos = models.JSONField(
        default=dict, blank=True,
        verbose_name="Dados Completos (JSON bruto)",
        help_text="Snapshot completo do JSON retornado pela API"
    )

    # --- Controle de sincronização --------------------------------------------
    data_atualizacao_hubsoft = models.DateTimeField(null=True, blank=True, verbose_name="Última Atualização Hubsoft")
    data_sync = models.DateTimeField(auto_now=True, verbose_name="Última Sincronização Local")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criado Localmente em")
    houve_alteracao = models.BooleanField(default=False, verbose_name="Houve Alteração na Última Sync")
    historico_alteracoes = models.JSONField(
        default=list, blank=True,
        verbose_name="Histórico de Alterações",
        help_text="Lista de diffs detectados entre sincronizações"
    )

    class Meta:
        db_table = 'clientes_hubsoft'
        verbose_name = "Cliente Hubsoft"
        verbose_name_plural = "👤 03. Clientes Hubsoft"
        ordering = ['-data_sync']
        indexes = [
            models.Index(fields=['cpf_cnpj']),
            models.Index(fields=['id_cliente']),
            models.Index(fields=['lead']),
        ]

    def __str__(self):
        status = "Ativo" if self.ativo else "Inativo"
        return f"{self.nome_razaosocial} (ID: {self.id_cliente}) — {status}"


class ServicoClienteHubsoft(TenantMixin):
    """
    Serviço contratado vinculado a um ClienteHubsoft.
    Cada cliente pode ter múltiplos serviços.
    """

    cliente = models.ForeignKey(
        ClienteHubsoft,
        on_delete=models.CASCADE,
        related_name='servicos',
        verbose_name="Cliente",
    )

    # --- Identificação do serviço ---------------------------------------------
    id_cliente_servico = models.IntegerField(unique=True, verbose_name="ID Cliente Serviço")
    uuid_cliente_servico = models.CharField(max_length=100, blank=True, default='', verbose_name="UUID")
    id_servico = models.IntegerField(null=True, blank=True, verbose_name="ID Serviço (Plano)")

    # --- Plano / valores ------------------------------------------------------
    numero_plano = models.IntegerField(null=True, blank=True, verbose_name="Número do Plano")
    nome = models.CharField(max_length=300, verbose_name="Nome do Plano")
    valor = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Valor (R$)")
    tecnologia = models.CharField(max_length=100, blank=True, default='', verbose_name="Tecnologia")
    velocidade_download = models.CharField(max_length=50, blank=True, default='', verbose_name="Download")
    velocidade_upload = models.CharField(max_length=50, blank=True, default='', verbose_name="Upload")

    # --- Status ---------------------------------------------------------------
    status = models.CharField(max_length=100, blank=True, default='', verbose_name="Status")
    status_prefixo = models.CharField(max_length=100, blank=True, default='', verbose_name="Status (prefixo)")

    # --- Datas ----------------------------------------------------------------
    data_habilitacao = models.DateTimeField(null=True, blank=True, verbose_name="Data Habilitação")
    data_venda = models.CharField(max_length=30, blank=True, default='', verbose_name="Data Venda")
    data_inicio_contrato = models.CharField(max_length=30, blank=True, default='', verbose_name="Início Contrato")
    data_fim_contrato = models.CharField(max_length=30, blank=True, default='', verbose_name="Fim Contrato")
    vigencia_meses = models.IntegerField(null=True, blank=True, verbose_name="Vigência (meses)")
    data_cadastro_servico = models.CharField(max_length=50, blank=True, default='', verbose_name="Data Cadastro")
    data_atualizacao_servico = models.DateTimeField(null=True, blank=True, verbose_name="Última Atualização")

    # --- Autenticação PPPoE ---------------------------------------------------
    id_cliente_servico_autenticacao = models.IntegerField(null=True, blank=True, verbose_name="ID Autenticação")
    login = models.CharField(max_length=100, blank=True, default='', verbose_name="Login PPPoE")
    senha = models.CharField(max_length=100, blank=True, default='', verbose_name="Senha PPPoE")
    mac_addr = models.CharField(max_length=30, blank=True, default='', verbose_name="MAC Address")
    phy_addr = models.CharField(max_length=30, blank=True, default='', verbose_name="PHY Address")
    vlan = models.CharField(max_length=30, blank=True, default='', verbose_name="VLAN")
    ipv4 = models.GenericIPAddressField(null=True, blank=True, verbose_name="IPv4")
    ipv6 = models.GenericIPAddressField(null=True, blank=True, protocol='IPv6', verbose_name="IPv6")

    # --- Cancelamento ---------------------------------------------------------
    id_motivo_cancelamento = models.IntegerField(null=True, blank=True, verbose_name="ID Motivo Cancelamento")
    data_cancelamento = models.DateTimeField(null=True, blank=True, verbose_name="Data Cancelamento")
    motivo_cancelamento = models.CharField(max_length=200, blank=True, default='', verbose_name="Motivo Cancelamento")

    # --- Vendedor -------------------------------------------------------------
    id_vendedor = models.IntegerField(null=True, blank=True, verbose_name="ID Vendedor")
    vendedor_nome = models.CharField(max_length=200, blank=True, default='', verbose_name="Nome Vendedor")
    vendedor_email = models.CharField(max_length=254, blank=True, default='', verbose_name="E-mail Vendedor")

    # --- Dados completos (backup) ---------------------------------------------
    dados_completos = models.JSONField(
        default=dict, blank=True,
        verbose_name="Dados Completos (JSON bruto)",
    )

    # --- Controle -------------------------------------------------------------
    data_sync = models.DateTimeField(auto_now=True, verbose_name="Última Sincronização")

    class Meta:
        db_table = 'servicos_cliente_hubsoft'
        verbose_name = "Serviço do Cliente Hubsoft"
        verbose_name_plural = "📦 04. Serviços de Clientes Hubsoft"
        ordering = ['-data_sync']
        indexes = [
            models.Index(fields=['id_cliente_servico']),
            models.Index(fields=['cliente']),
            models.Index(fields=['status_prefixo']),
        ]

    def __str__(self):
        return f"{self.nome} — {self.status} (ID: {self.id_cliente_servico})"
