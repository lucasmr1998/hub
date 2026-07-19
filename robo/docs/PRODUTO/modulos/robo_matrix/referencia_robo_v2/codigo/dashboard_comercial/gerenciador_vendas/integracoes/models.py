from django.db import models
from django.utils import timezone


class IntegracaoAPI(models.Model):
    """
    Armazena credenciais e configuração de APIs externas.
    Cada registro representa uma conexão com um sistema (Hubsoft, etc).
    """
    TIPO_CHOICES = [
        ('hubsoft', 'Hubsoft'),
        ('matrix', 'Matrix'),
        ('outro', 'Outro'),
    ]

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

    client_secret = models.CharField(
        max_length=500,
        verbose_name="Client Secret",
    )

    username = models.CharField(
        max_length=200,
        verbose_name="Usuário",
    )

    password = models.CharField(
        max_length=200,
        verbose_name="Senha",
    )

    grant_type = models.CharField(
        max_length=50,
        default='password',
        verbose_name="Grant Type",
    )

    # --- Token cacheado ---------------------------------------------------
    access_token = models.TextField(
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


class LogIntegracao(models.Model):
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
        'vendas_web.LeadProspecto',
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


class ClienteHubsoft(models.Model):
    """
    Espelho local do cliente retornado pela API GET /api/v1/integracao/cliente.
    Sincronizado periodicamente com o Hubsoft.
    """

    lead = models.ForeignKey(
        'vendas_web.LeadProspecto',
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


class ServicoClienteHubsoft(models.Model):
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


class AtendimentoHubsoft(models.Model):
    """
    Espelho local dos atendimentos de um ClienteHubsoft.
    Sincronizado periodicamente via API Hubsoft.
    """
    cliente = models.ForeignKey(
        ClienteHubsoft, on_delete=models.CASCADE, related_name='atendimentos',
        verbose_name="Cliente Hubsoft",
    )
    id_atendimento = models.BigIntegerField(unique=True, verbose_name="ID Atendimento")
    protocolo = models.CharField(max_length=50, blank=True, default='', db_index=True)
    tipo_atendimento = models.CharField(max_length=120, blank=True, default='')
    status = models.CharField(max_length=60, blank=True, default='', db_index=True)
    status_fechamento = models.CharField(max_length=60, blank=True, default='')
    motivo_fechamento = models.CharField(max_length=255, blank=True, default='')
    setor_responsavel = models.CharField(max_length=120, blank=True, default='')
    usuario_abertura = models.CharField(max_length=120, blank=True, default='')
    usuario_responsavel = models.CharField(max_length=120, blank=True, default='')
    usuario_fechamento = models.CharField(max_length=120, blank=True, default='')
    descricao_abertura = models.TextField(blank=True, default='')
    descricao_fechamento = models.TextField(blank=True, default='')
    data_cadastro = models.CharField(max_length=30, blank=True, default='')
    data_fechamento = models.CharField(max_length=30, blank=True, default='')
    rascunho = models.BooleanField(default=False)
    qtd_ordens_servico = models.PositiveIntegerField(default=0)
    dados_completos = models.JSONField(default=dict, blank=True)
    data_sync = models.DateTimeField(auto_now=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'atendimentos_hubsoft'
        verbose_name = "Atendimento Hubsoft"
        verbose_name_plural = "Atendimentos Hubsoft"
        ordering = ['-data_cadastro', '-id_atendimento']
        indexes = [
            models.Index(fields=['cliente', '-id_atendimento']),
            models.Index(fields=['protocolo']),
        ]

    def __str__(self):
        return f"Atend #{self.id_atendimento} — {self.tipo_atendimento}"


class OrdemServicoHubsoft(models.Model):
    """
    Espelho local das ordens de serviço de um ClienteHubsoft.
    """
    cliente = models.ForeignKey(
        ClienteHubsoft, on_delete=models.CASCADE, related_name='ordens_servico',
        verbose_name="Cliente Hubsoft",
    )
    atendimento = models.ForeignKey(
        AtendimentoHubsoft, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordens_servico_rel',
    )
    id_ordem_servico = models.BigIntegerField(unique=True, verbose_name="ID OS")
    numero_ordem_servico = models.CharField(max_length=60, blank=True, default='', db_index=True)
    tipo = models.CharField(max_length=120, blank=True, default='')
    status = models.CharField(max_length=60, blank=True, default='', db_index=True)
    status_fechamento = models.CharField(max_length=60, blank=True, default='')
    usuario_abertura = models.CharField(max_length=120, blank=True, default='')
    usuario_fechamento = models.CharField(max_length=120, blank=True, default='')
    descricao_abertura = models.TextField(blank=True, default='')
    descricao_servico = models.TextField(blank=True, default='')
    descricao_fechamento = models.TextField(blank=True, default='')
    data_cadastro = models.CharField(max_length=30, blank=True, default='')
    data_inicio_programado = models.CharField(max_length=30, blank=True, default='')
    data_termino_programado = models.CharField(max_length=30, blank=True, default='')
    data_inicio_executado = models.CharField(max_length=30, blank=True, default='')
    data_termino_executado = models.CharField(max_length=30, blank=True, default='')
    tecnicos = models.JSONField(default=list, blank=True)
    qtd_anexos = models.PositiveIntegerField(default=0)
    dados_completos = models.JSONField(default=dict, blank=True)
    data_sync = models.DateTimeField(auto_now=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ordens_servico_hubsoft'
        verbose_name = "Ordem de Serviço Hubsoft"
        verbose_name_plural = "Ordens de Serviço Hubsoft"
        ordering = ['-data_cadastro', '-id_ordem_servico']
        indexes = [
            models.Index(fields=['cliente', '-id_ordem_servico']),
            models.Index(fields=['numero_ordem_servico']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"OS #{self.numero_ordem_servico} — {self.status}"


class AgendamentoInstalacaoIA(models.Model):
    """Agendamento de instalação criado pelo fluxo IA (WhatsApp).

    Análogo ao AgendamentoInstalacao do site, mas SEM FK pra CadastroCliente
    (o fluxo IA não cria CadastroCliente — só LeadProspecto).

    Estados:
    - 'aguardando_sync': cliente ainda não tem ClienteHubsoft vinculado
                        (sync ainda não rodou). Worker reprocessa.
    - 'processando': worker está executando agora
    - 'agendado': consultar_agenda + abrir_atendimento + abrir_os deu certo
    - 'erro': falha persistente
    """
    STATUS_CHOICES = [
        ('aguardando_sync', 'Aguardando sync Hubsoft'),
        ('processando',     'Processando'),
        ('agendado',        'Agendado'),
        ('erro',            'Erro'),
    ]
    TURNO_CHOICES = [('manha', 'Manhã'), ('tarde', 'Tarde')]

    lead = models.ForeignKey(
        'vendas_web.LeadProspecto', on_delete=models.CASCADE,
        related_name='agendamentos_ia',
    )
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES)
    data_instalacao = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='aguardando_sync', db_index=True)

    # Dados resolvidos pela consulta_agenda
    horario = models.TimeField(null=True, blank=True)
    id_tecnico = models.IntegerField(null=True, blank=True)
    nome_tecnico = models.CharField(max_length=255, blank=True, default='')
    id_agenda_os = models.IntegerField(null=True, blank=True)

    # Dados vindos do Hubsoft (depois da sincronização)
    id_cliente_servico = models.IntegerField(null=True, blank=True)
    id_atendimento_matrix = models.IntegerField(null=True, blank=True)
    id_os_matrix = models.IntegerField(null=True, blank=True)

    dados_resposta_atendimento = models.JSONField(default=dict, blank=True)
    dados_resposta_os = models.JSONField(default=dict, blank=True)

    # Auditoria do worker
    tentativas = models.PositiveIntegerField(default=0)
    ultimo_erro = models.TextField(blank=True, default='')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    data_processado = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'agendamentos_instalacao_ia'
        verbose_name = 'Agendamento Instalação (IA)'
        verbose_name_plural = '📅 Agendamentos Instalação IA'
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['status', '-data_criacao']),
            models.Index(fields=['lead']),
        ]

    def __str__(self):
        return f'Agendamento IA #{self.pk} - lead {self.lead_id} - {self.status}'
