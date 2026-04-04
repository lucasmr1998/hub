from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.sistema.mixins import TenantMixin


class CampanhaTrafego(TenantMixin):
    """
    Modelo para gerenciar campanhas de tráfego pago com detecção por palavra-chave
    """
    PLATAFORMA_CHOICES = [
        ('google_ads', 'Google Ads'),
        ('facebook_ads', 'Facebook Ads'),
        ('instagram_ads', 'Instagram Ads'),
        ('tiktok_ads', 'TikTok Ads'),
        ('linkedin_ads', 'LinkedIn Ads'),
        ('email', 'Email Marketing'),
        ('sms', 'SMS Marketing'),
        ('whatsapp', 'WhatsApp Business'),
        ('outro', 'Outro'),
    ]

    TIPO_TRAFEGO_CHOICES = [
        ('pago', 'Tráfego Pago'),
        ('organico', 'Tráfego Orgânico'),
        ('hibrido', 'Híbrido'),
    ]

    TIPO_MATCH_CHOICES = [
        ('exato', 'Match Exato'),
        ('parcial', 'Match Parcial'),
        ('regex', 'Expressão Regular'),
    ]

    # Identificação
    nome = models.CharField(
        max_length=200,
        verbose_name="Nome da Campanha",
        help_text="Nome descritivo da campanha"
    )

    codigo = models.CharField(
        max_length=50,
        verbose_name="Código Único",
        help_text="Código identificador único (ex: BF2024, CUPOM50)"
    )

    descricao = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada da campanha"
    )

    # Palavra-chave (integrada)
    palavra_chave = models.CharField(
        max_length=200,
        verbose_name="Palavra-chave",
        help_text="Palavra ou termo que identifica esta campanha"
    )

    tipo_match = models.CharField(
        max_length=20,
        choices=TIPO_MATCH_CHOICES,
        default='parcial',
        verbose_name="Tipo de Detecção",
        help_text="Como a palavra-chave será detectada na mensagem"
    )

    case_sensitive = models.BooleanField(
        default=False,
        verbose_name="Case Sensitive",
        help_text="Diferenciar maiúsculas de minúsculas"
    )

    # Classificação
    plataforma = models.CharField(
        max_length=50,
        choices=PLATAFORMA_CHOICES,
        verbose_name="Plataforma",
        help_text="Plataforma de origem do tráfego"
    )

    tipo_trafego = models.CharField(
        max_length=50,
        choices=TIPO_TRAFEGO_CHOICES,
        blank=True,
        verbose_name="Tipo de Tráfego"
    )

    # Configurações
    prioridade = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Prioridade",
        help_text="Prioridade para desempate (1-10)"
    )

    ativa = models.BooleanField(
        default=True,
        verbose_name="Ativa",
        help_text="Se a campanha está ativa para detecção"
    )

    # Período
    data_inicio = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Início"
    )

    data_fim = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de Término"
    )

    # Comercial
    url_destino = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="URL de Destino",
        help_text="URL da landing page ou destino da campanha"
    )

    orcamento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Orçamento",
        help_text="Orçamento total da campanha em R$"
    )

    meta_leads = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Meta de Leads",
        help_text="Quantidade de leads esperada"
    )

    # Estatísticas (auto-calculadas)
    contador_deteccoes = models.IntegerField(
        default=0,
        verbose_name="Total de Detecções",
        help_text="Contador automático de detecções"
    )

    ultima_deteccao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última Detecção"
    )

    # UI/Visual
    cor_identificacao = models.CharField(
        max_length=7,
        default='#667eea',
        verbose_name="Cor de Identificação",
        help_text="Cor hexadecimal para identificação visual"
    )

    ordem_exibicao = models.IntegerField(
        default=0,
        verbose_name="Ordem de Exibição"
    )

    # Metadados
    observacoes = models.TextField(
        blank=True,
        verbose_name="Observações"
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Criado por"
    )

    class Meta:
        db_table = 'campanha_trafego'
        verbose_name = "Campanha de Tráfego"
        verbose_name_plural = "📢 Campanhas de Tráfego"
        ordering = ['-ativa', 'ordem_exibicao', 'nome']
        unique_together = ('tenant', 'codigo')
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['ativa']),
            models.Index(fields=['palavra_chave']),
            models.Index(fields=['plataforma']),
        ]

    def __str__(self):
        return f"{self.nome} ({self.codigo})"

    @property
    def esta_no_periodo(self):
        """Verifica se a campanha está dentro do período ativo"""
        from datetime import date
        hoje = date.today()

        if self.data_inicio and hoje < self.data_inicio:
            return False
        if self.data_fim and hoje > self.data_fim:
            return False
        return True

    @property
    def esta_ativa(self):
        """Verifica se a campanha está ativa E dentro do período"""
        return self.ativa and self.esta_no_periodo

    @property
    def total_leads(self):
        """Total de leads gerados por esta campanha"""
        from apps.comercial.leads.models import LeadProspecto
        return LeadProspecto.objects.filter(campanha_origem=self).count()

    @property
    def total_conversoes(self):
        """Total de vendas convertidas"""
        return self.deteccoes.filter(converteu_venda=True).count()

    @property
    def taxa_conversao(self):
        """Taxa de conversão percentual"""
        if self.contador_deteccoes == 0:
            return 0
        return round((self.total_conversoes / self.contador_deteccoes) * 100, 2)

    @property
    def receita_total(self):
        """Receita total gerada pela campanha"""
        from django.db.models import Sum
        total = self.deteccoes.filter(converteu_venda=True).aggregate(
            total=Sum('valor_venda')
        )['total']
        return total or Decimal('0.00')

    @property
    def roi(self):
        """Retorno sobre investimento"""
        if not self.orcamento or self.orcamento == 0:
            return None
        return round(((self.receita_total - self.orcamento) / self.orcamento) * 100, 2)


class DeteccaoCampanha(TenantMixin):
    """
    Modelo para registrar detecções de campanhas em mensagens de clientes
    """
    ORIGEM_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('chat', 'Chat Web'),
        ('telefone', 'Telefone'),
    ]

    METODO_DETECCAO_CHOICES = [
        ('exato', 'Match Exato'),
        ('parcial', 'Match Parcial'),
        ('regex', 'Expressão Regular'),
    ]

    # Relacionamentos
    lead = models.ForeignKey(
        'leads.LeadProspecto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deteccoes_campanha',
        verbose_name="Lead"
    )

    campanha = models.ForeignKey(
        CampanhaTrafego,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deteccoes',
        verbose_name="Campanha"
    )

    # Dados da Mensagem
    telefone = models.CharField(
        max_length=20,
        verbose_name="Telefone"
    )

    mensagem_original = models.TextField(
        verbose_name="Mensagem Original"
    )

    mensagem_normalizada = models.TextField(
        blank=True,
        verbose_name="Mensagem Normalizada",
        help_text="Versão normalizada para processamento"
    )

    tamanho_mensagem = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Tamanho da Mensagem"
    )

    # Detecção
    trecho_detectado = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Trecho Detectado",
        help_text="Parte da mensagem que deu match"
    )

    posicao_inicio = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Posição Inicial"
    )

    posicao_fim = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Posição Final"
    )

    metodo_deteccao = models.CharField(
        max_length=20,
        choices=METODO_DETECCAO_CHOICES,
        blank=True,
        verbose_name="Método de Detecção"
    )

    score_confianca = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Score de Confiança",
        help_text="Percentual de confiança (0-100%)"
    )

    # Contexto
    eh_primeira_mensagem = models.BooleanField(
        default=False,
        verbose_name="É Primeira Mensagem",
        help_text="Se é a primeira mensagem do cliente"
    )

    origem = models.CharField(
        max_length=20,
        choices=ORIGEM_CHOICES,
        default='whatsapp',
        verbose_name="Origem"
    )

    timestamp_mensagem = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Timestamp da Mensagem"
    )

    # Dados Técnicos
    ip_origem = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP de Origem"
    )

    user_agent = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="User Agent"
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadata",
        help_text="Dados adicionais em formato JSON"
    )

    # Validação Manual
    aceita = models.BooleanField(
        default=True,
        verbose_name="Detecção Aceita",
        help_text="Se a detecção foi validada como correta"
    )

    motivo_rejeicao = models.TextField(
        blank=True,
        verbose_name="Motivo da Rejeição"
    )

    rejeitada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deteccoes_rejeitadas',
        verbose_name="Rejeitada por"
    )

    data_rejeicao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Rejeição"
    )

    # Integração N8N
    processado_n8n = models.BooleanField(
        default=False,
        verbose_name="Processado pelo N8N"
    )

    data_processamento_n8n = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Processamento N8N"
    )

    resposta_n8n = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Resposta do N8N"
    )

    # Conversão
    converteu_venda = models.BooleanField(
        default=False,
        verbose_name="Converteu em Venda"
    )

    data_conversao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Conversão"
    )

    valor_venda = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor da Venda"
    )

    # Auditoria
    detectado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Detectado em"
    )

    class Meta:
        db_table = 'deteccao_campanha'
        verbose_name = "Detecção de Campanha"
        verbose_name_plural = "📊 Detecções de Campanhas"
        ordering = ['-detectado_em']
        indexes = [
            models.Index(fields=['telefone']),
            models.Index(fields=['lead']),
            models.Index(fields=['campanha']),
            models.Index(fields=['-detectado_em']),
            models.Index(fields=['aceita']),
            models.Index(fields=['converteu_venda']),
        ]

    def __str__(self):
        campanha_nome = self.campanha.nome if self.campanha else "Sem campanha"
        return f"{campanha_nome} - {self.telefone} - {self.detectado_em.strftime('%d/%m/%Y %H:%M')}"

    def save(self, *args, **kwargs):
        # Normalizar mensagem automaticamente
        if self.mensagem_original and not self.mensagem_normalizada:
            import unicodedata
            self.mensagem_normalizada = unicodedata.normalize('NFKD', self.mensagem_original.lower())
            self.mensagem_normalizada = self.mensagem_normalizada.encode('ASCII', 'ignore').decode('ASCII')

        # Calcular tamanho
        if self.mensagem_original:
            self.tamanho_mensagem = len(self.mensagem_original)

        super().save(*args, **kwargs)

        # Atualizar contador da campanha
        if self.campanha and self.aceita:
            self.campanha.contador_deteccoes = self.campanha.deteccoes.filter(aceita=True).count()
            self.campanha.ultima_deteccao = timezone.now()
            self.campanha.save()
