from datetime import time

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

from apps.sistema.mixins import TenantMixin


class TipoNotificacao(TenantMixin):
    """Tipos de notificações disponíveis no sistema"""
    TIPOS = [
        ('lead_novo', 'Novo Lead'),
        ('lead_convertido', 'Lead Convertido'),
        ('venda_aprovada', 'Venda Aprovada'),
        ('venda_rejeitada', 'Venda Rejeitada'),
        ('prospecto_aguardando', 'Prospecto Aguardando Validação'),
    ]

    codigo = models.CharField(
        max_length=50,
        choices=TIPOS,
        verbose_name="Código"
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome"
    )
    descricao = models.TextField(
        verbose_name="Descrição"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    template_padrao = models.TextField(
        verbose_name="Template Padrão",
        help_text="Template padrão da mensagem"
    )
    prioridade_padrao = models.CharField(
        max_length=20,
        choices=[
            ('baixa', 'Baixa'),
            ('normal', 'Normal'),
            ('alta', 'Alta'),
            ('urgente', 'Urgente'),
        ],
        default='normal',
        verbose_name="Prioridade Padrão"
    )
    whatsapp_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuração WhatsApp",
        help_text="Configurações específicas para o canal WhatsApp"
    )

    class Meta:
        verbose_name = "Tipo de Notificação"
        verbose_name_plural = "📢 01. Tipos de Notificação"
        ordering = ['nome']
        unique_together = ('tenant', 'codigo')

    def __str__(self):
        return self.nome


class CanalNotificacao(TenantMixin):
    """Canais de notificação disponíveis"""
    CANAIS = [
        ('whatsapp', 'WhatsApp'),
        ('webhook', 'Webhook'),
    ]

    codigo = models.CharField(
        max_length=20,
        choices=CANAIS,
        verbose_name="Código"
    )
    nome = models.CharField(
        max_length=50,
        verbose_name="Nome"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    configuracao = models.JSONField(
        default=dict,
        verbose_name="Configuração",
        help_text="Configurações específicas do canal"
    )
    icone = models.CharField(
        max_length=50,
        default="fas fa-envelope",
        verbose_name="Ícone",
        help_text="Classe do ícone FontAwesome"
    )

    class Meta:
        verbose_name = "Canal de Notificação"
        verbose_name_plural = "📱 02. Canais de Notificação"
        ordering = ['nome']
        unique_together = ('tenant', 'codigo')

    def __str__(self):
        return self.nome


class PreferenciaNotificacao(TenantMixin):
    """Preferências de notificação por usuário"""
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='preferencias_notificacao'
    )
    tipo_notificacao = models.ForeignKey(
        TipoNotificacao,
        on_delete=models.CASCADE
    )
    canal_preferido = models.ForeignKey(
        CanalNotificacao,
        on_delete=models.CASCADE
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    horario_inicio = models.TimeField(
        default=time(8, 0),
        verbose_name="Horário Início",
        help_text="Horário início para receber notificações"
    )
    horario_fim = models.TimeField(
        default=time(18, 0),
        verbose_name="Horário Fim",
        help_text="Horário fim para receber notificações"
    )
    dias_semana = models.JSONField(
        default=list,
        verbose_name="Dias da Semana",
        help_text="Dias da semana [0=segunda, 6=domingo]"
    )

    class Meta:
        unique_together = ['usuario', 'tipo_notificacao', 'canal_preferido']
        verbose_name = "Preferência de Notificação"
        verbose_name_plural = "⚙️ 03. Preferências de Notificação"
        ordering = ['usuario__username', 'tipo_notificacao__nome']

    def __str__(self):
        return f"{self.usuario.username} - {self.tipo_notificacao.nome}"


class Notificacao(TenantMixin):
    """Registro de notificações enviadas"""
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviando', 'Enviando'),
        ('enviada', 'Enviada'),
        ('falhou', 'Falhou'),
        ('cancelada', 'Cancelada'),
    ]

    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]

    # Dados básicos
    tipo = models.ForeignKey(
        TipoNotificacao,
        on_delete=models.CASCADE
    )
    canal = models.ForeignKey(
        CanalNotificacao,
        on_delete=models.CASCADE
    )
    destinatario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    destinatario_email = models.EmailField(
        null=True,
        blank=True
    )
    destinatario_telefone = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    # Conteúdo
    titulo = models.CharField(
        max_length=200,
        verbose_name="Título"
    )
    mensagem = models.TextField(
        verbose_name="Mensagem"
    )
    dados_contexto = models.JSONField(
        default=dict,
        verbose_name="Dados de Contexto",
        help_text="Dados para personalização"
    )

    # Controle
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente'
    )
    prioridade = models.CharField(
        max_length=20,
        choices=PRIORIDADE_CHOICES,
        default='normal'
    )
    tentativas = models.PositiveIntegerField(
        default=0
    )
    max_tentativas = models.PositiveIntegerField(
        default=3
    )

    # Timestamps
    data_criacao = models.DateTimeField(
        default=timezone.now
    )
    data_envio = models.DateTimeField(
        null=True,
        blank=True
    )
    data_agendamento = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Para envio agendado"
    )

    # N8N Integration
    n8n_webhook_id = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    n8n_execution_id = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    n8n_response = models.JSONField(
        null=True,
        blank=True
    )

    # Logs
    erro_detalhes = models.TextField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "📨 04. Notificações"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['data_criacao']),
            models.Index(fields=['tipo']),
            models.Index(fields=['canal']),
        ]

    def __str__(self):
        return f"{self.tipo.nome} - {self.destinatario or self.destinatario_email}"


class TemplateNotificacao(TenantMixin):
    """Templates de notificação por canal"""
    tipo_notificacao = models.ForeignKey(
        TipoNotificacao,
        on_delete=models.CASCADE
    )
    canal = models.ForeignKey(
        CanalNotificacao,
        on_delete=models.CASCADE
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome do Template"
    )
    assunto = models.CharField(
        max_length=200,
        verbose_name="Assunto",
        help_text="Assunto para email"
    )
    corpo_html = models.TextField(
        verbose_name="Corpo HTML",
        help_text="Template HTML"
    )
    corpo_texto = models.TextField(
        verbose_name="Corpo Texto",
        help_text="Template texto simples"
    )
    variaveis = models.JSONField(
        default=list,
        verbose_name="Variáveis",
        help_text="Lista de variáveis disponíveis"
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )

    class Meta:
        unique_together = ['tipo_notificacao', 'canal']
        verbose_name = "Template de Notificação"
        verbose_name_plural = "📝 05. Templates de Notificação"
        ordering = ['tipo_notificacao__nome', 'canal__nome']

    def __str__(self):
        return f"{self.tipo_notificacao.nome} - {self.canal.nome}"
