from django.db import models
from django.utils import timezone

from apps.sistema.encrypted_fields import EncryptedCharField, EncryptedTextField
from apps.sistema.mixins import TenantMixin

# Audit log dos webhooks publicos N8N (registro/alerta de 500) — declarado em
# models_audit.py pra organizar; importa aqui pro Django registrar.
from .models_audit import LogWebhookN8N  # noqa: F401

# Tentativas de abertura de OS via Matrix (painel /integracoes/ordens-servico/)
from .models_os import OrdemServicoTentativa  # noqa: F401

# Tentativas de criar/aceitar contrato HubSoft (painel /integracoes/contratos/)
from .models_contrato import ContratoTentativa  # noqa: F401

# Espelhos de dados HubSoft pra alimentar relatorios + modulo CS
from .models_hubsoft_relatorios import (  # noqa: F401
    FaturaHubsoft,
    OrdemServicoHubsoft,
    AtendimentoHubsoft,
)

# Ultimo export de CRM do HubSoft (aba Oportunidades das inconsistencias)
from .models_crm_import import ImportacaoCRMHubsoft  # noqa: F401


class IntegracaoAPI(TenantMixin):
    """
    Armazena credenciais e configuração de APIs externas.
    Cada registro representa uma conexão com um sistema (Hubsoft, etc).
    """
    TIPO_CHOICES = [
        ('hubsoft', 'HubSoft'),
        ('sgp', 'SGP (inSystem)'),
        ('uazapi', 'Uazapi (WhatsApp)'),
        ('evolution', 'Evolution API (WhatsApp)'),
        ('meta_cloud', 'Meta Cloud API (WhatsApp)'),
        ('twilio_whatsapp', 'Twilio (WhatsApp)'),
        ('n8n', 'N8N (Automação)'),
        ('talk', 'Talk (Matrix do Brasil - PABX)'),
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
        blank=True, default='',
        verbose_name="URL Base da API",
        help_text="Opcional para OpenAI/Anthropic/Groq (usa URL padrao)"
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

    # --- API Key (para providers de IA: OpenAI, Anthropic, Groq, etc.) ----
    api_key = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name="API Key",
        help_text="Chave de API do provider (OpenAI, Anthropic, Groq, etc.)"
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

    def save(self, *args, **kwargs):
        """Audita zeramento do cache. Quando configuracoes_extras.cache[X]
        vai de N>0 itens pra 0 ou some, registra LogSistema com WARNING e
        identifica o caller. Resolve o bug recorrente "id_origem 15
        inativado" causado por cache.origens_cliente esvaziado em algum
        path desconhecido. Nao bloqueia o save, so audita.
        """
        if self.pk:
            try:
                self._auditar_zeramento_cache()
            except Exception:
                # Auditoria nunca bloqueia o save
                import logging
                logging.getLogger(__name__).exception('[IntegracaoAPI] Falhou auditoria de cache')
        super().save(*args, **kwargs)

    def _auditar_zeramento_cache(self):
        antigo = type(self).all_tenants.filter(pk=self.pk).only('configuracoes_extras').first()
        if not antigo:
            return
        cache_antigo = (antigo.configuracoes_extras or {}).get('cache') or {}
        cache_novo = (self.configuracoes_extras or {}).get('cache') or {}
        zerados = []
        for k, v_antigo in cache_antigo.items():
            if not isinstance(v_antigo, list) or len(v_antigo) == 0:
                continue
            v_novo = cache_novo.get(k, [])
            if not isinstance(v_novo, list) or len(v_novo) == 0:
                zerados.append({'chave': k, 'antes': len(v_antigo), 'depois': len(v_novo) if isinstance(v_novo, list) else 0})
        if not zerados:
            return
        import inspect
        caller = '?'
        try:
            for fr in inspect.stack()[2:14]:
                fn = fr.filename.replace('\\', '/')
                if '/django/' in fn or 'models.py' in fn:
                    continue
                partes = fn.rsplit('/apps/', 1)
                curto = ('apps/' + partes[1]) if len(partes) == 2 else fn.rsplit('/', 1)[-1]
                caller = f"{curto}:{fr.lineno} {fr.function}"
                break
        except Exception:
            pass
        try:
            from apps.sistema.models import LogSistema
            LogSistema.all_tenants.create(
                tenant=self.tenant,
                categoria='integracao', acao='cache_zerado',
                entidade='IntegracaoAPI', entidade_id=self.pk,
                nivel='WARNING',
                mensagem=f'Cache de IntegracaoAPI {self.pk} ({self.tipo}) zerado em {len(zerados)} chave(s). Caller: {caller}',
                dados_extras={'zerados': zerados, 'caller': caller},
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                '[IntegracaoAPI %s] cache zerado: %s caller=%s',
                self.pk, zerados, caller,
            )

    @property
    def token_valido(self):
        """Retorna True se o token cacheado ainda está válido."""
        if not self.access_token or not self.token_expira_em:
            return False
        return timezone.now() < self.token_expira_em

    @property
    def token_uazapi(self):
        """Token limpo do Uazapi (de configuracoes_extras, sem encriptacao)."""
        extras = self.configuracoes_extras or {}
        return extras.get('token', '')

    # --- Modos de sincronização -------------------------------------------

    SYNC_MODOS = ['automatico', 'manual', 'desativado']

    SYNC_FEATURES = {
        'enviar_lead': 'Enviar lead ao criar',
        'sincronizar_cliente': 'Sincronizar dados do cliente',
        'sincronizar_servicos': 'Sincronizar servicos contratados',
        'sincronizar_planos': 'Sincronizar catalogo de planos (ERP -> ProdutoServico)',
        'sincronizar_vencimentos': 'Sincronizar opcoes de vencimento (ERP -> OpcaoVencimentoCRM)',
        'sincronizar_vendedores': 'Sincronizar vendedores (ERP -> configuracoes_extras.cache)',
        'sincronizar_pops': 'Sincronizar POPs (ERP -> configuracoes_extras.cache)',
        'sincronizar_portadores': 'Sincronizar portadores financeiros (ERP -> configuracoes_extras.cache)',
        'anexar_documentos_contrato': 'Anexar documentos validados ao contrato (HubSoft)',
        'aceitar_contrato': 'Aceitar contrato apos anexar documentos (HubSoft)',
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

    # --- Churn score (rule-based) — atualizado pelo cron atualizar_churn_score
    churn_score = models.IntegerField(
        null=True, blank=True, db_index=True,
        verbose_name="Score de Churn (0-100)",
        help_text="Quanto maior, maior o risco de cancelamento. Threshold sugerido: 60+",
    )
    churn_sinais = models.JSONField(
        default=dict, blank=True,
        verbose_name="Sinais de churn",
        help_text="Breakdown dos sinais que compuseram o score. Ex: {'inadimplente': 25, 'tickets_abertos': 30}",
    )
    churn_atualizado_em = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Score atualizado em",
    )

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

    # --- Contrato (gerado via HubSoft /adicionar_contrato) --------------------
    id_cliente_servico_contrato = models.IntegerField(
        null=True, blank=True, db_index=True,
        verbose_name="ID Contrato HubSoft",
        help_text="ID do contrato gerado via /api/v1/integracao/cliente/contrato/adicionar_contrato. Preenchido pela acao de automacao gerar_contrato_hubsoft.",
    )

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


class ClienteSGP(TenantMixin):
    """
    Espelho local do cliente vindo da API SGP (POST /api/ura/consultacliente/).
    Schema diferente do ClienteHubsoft: contratos vem aninhados na resposta,
    nao ha uuid_cliente, e o id_cliente do SGP nao e globalmente unico — e
    unico DENTRO do tenant SGP do provedor (gigamax.sgp.net.br tem ids
    diferentes de outroprovedor.sgp.net.br).
    """

    integracao = models.ForeignKey(
        'integracoes.IntegracaoAPI',
        on_delete=models.CASCADE,
        related_name='clientes_sgp',
        verbose_name='Integracao SGP de origem',
        help_text='Garante que id_cliente_sgp e unico por integracao, nao globalmente.',
    )

    lead = models.ForeignKey(
        'leads.LeadProspecto',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clientes_sgp',
        verbose_name='Lead de origem',
    )

    # --- Identificacao SGP ---
    id_cliente_sgp = models.IntegerField(
        verbose_name='ID Cliente no SGP',
        help_text='Retornado em new_cliente_id ao cadastrar e em consultas.',
        db_index=True,
    )
    precadastro_id = models.IntegerField(
        null=True, blank=True,
        verbose_name='ID Pre-cadastro SGP',
        help_text='So preenchido quando o cliente veio via cadastrar_prospecto_pf.',
    )

    # --- Dados pessoais ---
    nome = models.CharField(max_length=300, verbose_name='Nome')
    cpf_cnpj = models.CharField(max_length=20, db_index=True, verbose_name='CPF/CNPJ')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    telefone = models.CharField(max_length=30, blank=True, default='', verbose_name='Telefone')

    # --- Endereco ---
    cep = models.CharField(max_length=10, blank=True, default='', verbose_name='CEP')
    logradouro = models.CharField(max_length=255, blank=True, default='', verbose_name='Logradouro')
    numero = models.CharField(max_length=20, blank=True, default='', verbose_name='Numero')
    bairro = models.CharField(max_length=120, blank=True, default='', verbose_name='Bairro')
    cidade = models.CharField(max_length=100, blank=True, default='', verbose_name='Cidade')
    uf = models.CharField(max_length=2, blank=True, default='', verbose_name='UF')

    # --- Status ---
    ativo = models.BooleanField(default=True, verbose_name='Ativo no SGP')

    # --- Aninhados como JSON (SGP retorna estruturas variaveis) ---
    contratos = models.JSONField(default=list, blank=True, verbose_name='Contratos')
    dados_completos = models.JSONField(
        default=dict, blank=True,
        verbose_name='Snapshot da resposta SGP',
        help_text='JSON cru de POST /api/ura/consultacliente/ — fonte de verdade.',
    )

    # --- Controle de sync ---
    data_sync = models.DateTimeField(auto_now=True, verbose_name='Ultima sync')
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    houve_alteracao = models.BooleanField(default=False, verbose_name='Houve alteracao na ultima sync')
    historico_alteracoes = models.JSONField(default=list, blank=True, verbose_name='Historico de alteracoes')

    class Meta:
        db_table = 'clientes_sgp'
        verbose_name = 'Cliente SGP'
        verbose_name_plural = '👤 05. Clientes SGP'
        ordering = ['-data_sync']
        constraints = [
            models.UniqueConstraint(
                fields=['integracao', 'id_cliente_sgp'],
                name='unique_cliente_sgp_por_integracao',
            ),
        ]
        indexes = [
            models.Index(fields=['cpf_cnpj']),
            models.Index(fields=['lead']),
            models.Index(fields=['integracao', 'id_cliente_sgp']),
        ]

    def __str__(self):
        return f'{self.nome} (SGP id={self.id_cliente_sgp})'


class ConfiguracaoChurnScore(TenantMixin):
    """
    Configuração por tenant dos pesos e thresholds do scanner de churn.

    Singleton por tenant — usa get_or_create_default(tenant). Cada sinal é
    ligável independentemente, com peso ajustável e parâmetros específicos.

    Defaults sensatos (heurística do Hubtrix). Tenant pode customizar pra
    sua realidade — ex: ISP sem módulo NPS desliga o sinal NPS, ISP com
    histórico de inadimplência diferente ajusta o peso.
    """
    # === Sinal: Inadimplência ===
    inadimplencia_ativo = models.BooleanField(default=True, verbose_name='Inadimplência: ativo')
    inadimplencia_peso = models.PositiveSmallIntegerField(default=25, verbose_name='Inadimplência: peso')

    # === Sinal: Múltiplos tickets abertos ===
    multiplos_tickets_ativo = models.BooleanField(default=True, verbose_name='Múltiplos tickets: ativo')
    multiplos_tickets_peso = models.PositiveSmallIntegerField(default=30, verbose_name='Múltiplos tickets: peso')
    multiplos_tickets_minimo = models.PositiveSmallIntegerField(
        default=2, verbose_name='Múltiplos tickets: qtd mínima',
        help_text='Quantidade mínima de tickets abertos pra acionar este sinal',
    )

    # === Sinal: 1 ticket aberto ===
    ticket_aberto_ativo = models.BooleanField(default=True, verbose_name='Ticket aberto: ativo')
    ticket_aberto_peso = models.PositiveSmallIntegerField(default=10, verbose_name='Ticket aberto: peso')

    # === Sinal: Sem atividade ===
    sem_atividade_ativo = models.BooleanField(default=True, verbose_name='Sem atividade: ativo')
    sem_atividade_peso = models.PositiveSmallIntegerField(default=20, verbose_name='Sem atividade: peso')
    sem_atividade_dias = models.PositiveSmallIntegerField(
        default=30, verbose_name='Sem atividade: janela em dias',
        help_text='Sem conversas nos últimos N dias = aciona',
    )

    # === Sinal: Cliente novo ===
    cliente_novo_ativo = models.BooleanField(default=True, verbose_name='Cliente novo: ativo')
    cliente_novo_peso = models.PositiveSmallIntegerField(default=10, verbose_name='Cliente novo: peso')
    cliente_novo_meses = models.PositiveSmallIntegerField(
        default=6, verbose_name='Cliente novo: corte em meses',
        help_text='Cliente com menos de N meses entra na curva da banheira inicial',
    )

    # === Sinal: Cliente longo ===
    cliente_longo_ativo = models.BooleanField(default=True, verbose_name='Cliente longo: ativo')
    cliente_longo_peso = models.PositiveSmallIntegerField(default=5, verbose_name='Cliente longo: peso')
    cliente_longo_meses = models.PositiveSmallIntegerField(
        default=36, verbose_name='Cliente longo: corte em meses',
        help_text='Cliente com mais de N meses na outra ponta da banheira',
    )

    # === Sinal: NPS detrator (placeholder até módulo NPS) ===
    nps_detrator_ativo = models.BooleanField(
        default=False, verbose_name='NPS detrator: ativo',
        help_text='Ative quando módulo NPS estiver configurado',
    )
    nps_detrator_peso = models.PositiveSmallIntegerField(default=25, verbose_name='NPS detrator: peso')

    # === Thresholds de classificação ===
    threshold_atencao = models.PositiveSmallIntegerField(
        default=40, verbose_name='Threshold atenção',
        help_text='Score >= este valor mas < alto_risco classifica como atenção',
    )
    threshold_alto_risco = models.PositiveSmallIntegerField(
        default=60, verbose_name='Threshold alto risco',
        help_text='Score >= este valor classifica como alto risco. Notifica gerentes.',
    )

    # === Notificações ===
    notificar_em_alto_risco = models.BooleanField(
        default=True, verbose_name='Notificar gerentes ao entrar em alto risco',
    )

    # === Auditoria ===
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integracoes_config_churn_score'
        verbose_name = 'Configuração de Churn Score'
        verbose_name_plural = '⚙️ Config Churn Score (1 por tenant)'

    def __str__(self):
        return f'Config Churn Score · {self.tenant}'

    @classmethod
    def get_or_create_default(cls, tenant):
        """Singleton por tenant. Cria com defaults se não existir."""
        config, _ = cls.objects.get_or_create(tenant=tenant)
        return config

    def restaurar_padroes(self):
        """Reseta todos os campos pros defaults do Hubtrix."""
        for f in self._meta.fields:
            if f.name in ('id', 'tenant', 'atualizado_em'):
                continue
            if f.has_default():
                setattr(self, f.name, f.get_default())
        self.save()


class ClienteConsolidado(TenantMixin):
    """
    Cache normalizado de cliente vindo de qualquer ERP.

    Resolve o problema de scanners (churn, inadimplência, dashboards) precisarem
    funcionar consistentemente sem importar de qual ERP veio o cliente.

    Cada adapter (HubSoft, SGP, Voalle, ...) popula essa tabela com os mesmos
    campos normalizados. Scanners leem só daqui — agnósticos de ERP.

    Identidade: chave dupla (origem, id_origem) é única.
    cpf_cnpj é índice secundário pra cruzar mesmo CPF entre múltiplos ERPs.
    """
    ORIGEM_CHOICES = [
        ('hubsoft', 'HubSoft'),
        ('sgp', 'SGP / inSystem'),
        ('voalle', 'Voalle'),
        ('mk_auth', 'MK-Auth'),
        ('ixc', 'IXC'),
        ('manual', 'Cadastro manual no Hubtrix'),
    ]

    FORMA_COBRANCA_CHOICES = [
        ('boleto', 'Boleto'),
        ('pix', 'Pix'),
        ('cartao', 'Cartão'),
        ('misto', 'Misto'),
        ('outro', 'Outro / não informado'),
    ]

    TECNOLOGIA_CHOICES = [
        ('fibra', 'Fibra óptica'),
        ('radio', 'Rádio'),
        ('cabo', 'Cabo metálico'),
        ('outro', 'Outro'),
    ]

    # === Identidade & origem ===
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, db_index=True, verbose_name='Origem')
    id_origem = models.CharField(max_length=100, db_index=True, verbose_name='ID no ERP de origem')
    cpf_cnpj = models.CharField(max_length=20, blank=True, default='', db_index=True, verbose_name='CPF/CNPJ')

    # === Pessoa ===
    nome = models.CharField(max_length=300, verbose_name='Nome / Razão Social')
    email = models.EmailField(blank=True, default='', verbose_name='E-mail')
    telefone = models.CharField(max_length=30, blank=True, default='', verbose_name='Telefone')

    # === Vínculo com Hubtrix ===
    lead = models.ForeignKey(
        'leads.LeadProspecto',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clientes_consolidados',
        verbose_name='Lead vinculado',
    )

    # === Cliente — relacionamento com ISP ===
    data_virou_cliente = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Data de início do relacionamento',
        help_text='Quando assinou primeiro contrato',
    )
    meses_como_cliente = models.FloatField(
        null=True, blank=True,
        verbose_name='Meses como cliente',
    )
    cliente_ativo = models.BooleanField(default=True, db_index=True, verbose_name='Cliente ativo')
    cliente_suspenso = models.BooleanField(default=False, verbose_name='Cliente suspenso')

    # === Contratos / planos ===
    contratos_ativos_qtd = models.IntegerField(default=0, verbose_name='Contratos ativos')
    valor_mensal_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Valor mensal total (R$)',
    )
    planos_resumo = models.JSONField(
        default=list, blank=True,
        verbose_name='Resumo de planos',
        help_text='[{nome, valor, velocidade, status}]',
    )

    # === Financeiro ===
    inadimplente = models.BooleanField(default=False, db_index=True, verbose_name='Inadimplente')
    dias_em_atraso = models.IntegerField(null=True, blank=True, verbose_name='Dias em atraso')
    historico_atrasos_qtd = models.IntegerField(default=0, verbose_name='Histórico de atrasos')
    forma_cobranca = models.CharField(
        max_length=20, choices=FORMA_COBRANCA_CHOICES, blank=True, default='',
        verbose_name='Forma de cobrança predominante',
    )

    # === Suporte ===
    tickets_abertos_qtd = models.IntegerField(default=0, verbose_name='Tickets abertos')
    tickets_30d_qtd = models.IntegerField(default=0, verbose_name='Tickets últimos 30d')

    # === Tecnologia (ISP-specific, opcional) ===
    tecnologia = models.CharField(
        max_length=20, choices=TECNOLOGIA_CHOICES, blank=True, default='',
        verbose_name='Tecnologia',
    )
    cto_id_origem = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='CTO/POP ID no ERP',
    )
    uso_banda_pct_queda_60d = models.FloatField(
        null=True, blank=True,
        verbose_name='Queda no uso de banda 60d (%)',
        help_text='% de queda no uso médio nos últimos 60d vs 60d anteriores',
    )

    # === Engajamento (Hubtrix internal) ===
    ultima_conversa_em = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Última conversa no Inbox',
    )
    nps_ultimo = models.IntegerField(
        null=True, blank=True,
        verbose_name='Última nota NPS',
        help_text='0-10. Detrator <= 6, neutro 7-8, promotor 9-10.',
    )

    # === Cache / sync ===
    sincronizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Último sync no Hubtrix',
    )
    sync_origem_em = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Quando dado foi puxado do ERP',
    )
    dados_brutos = models.JSONField(
        default=dict, blank=True,
        verbose_name='Dados brutos do ERP (debug)',
    )

    class Meta:
        db_table = 'integracoes_cliente_consolidado'
        verbose_name = 'Cliente Consolidado'
        verbose_name_plural = '🌐 Clientes Consolidados (multi-ERP)'
        unique_together = [['origem', 'id_origem']]
        indexes = [
            models.Index(fields=['cpf_cnpj']),
            models.Index(fields=['inadimplente', '-dias_em_atraso']),
            models.Index(fields=['cliente_ativo', 'origem']),
            models.Index(fields=['-sincronizado_em']),
        ]

    def __str__(self):
        return f'{self.nome} ({self.get_origem_display()} #{self.id_origem})'
