from datetime import time

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

from apps.sistema.mixins import TenantMixin


class TipoNotificacao(TenantMixin):
    """Tipos de notificações disponíveis no sistema"""
    TIPOS = [
        # Comercial
        ('lead_novo', 'Novo Lead'),
        ('lead_convertido', 'Lead Convertido'),
        ('venda_aprovada', 'Venda Aprovada'),
        ('venda_rejeitada', 'Venda Rejeitada'),
        ('prospecto_aguardando', 'Prospecto Aguardando Validação'),
        # Inbox
        ('conversa_recebida', 'Nova Conversa Recebida'),
        ('conversa_transferida', 'Conversa Transferida'),
        ('mensagem_recebida', 'Nova Mensagem'),
        # CRM
        ('tarefa_vencendo', 'Tarefa Próxima do Vencimento'),
        ('tarefa_atribuida', 'Tarefa Atribuída'),
        ('oportunidade_movida', 'Oportunidade Mudou de Estágio'),
        # Suporte
        ('ticket_criado', 'Novo Ticket'),
        ('ticket_respondido', 'Ticket Respondido'),
        ('sla_estourando', 'SLA Próximo do Limite'),
        # Sistema
        ('mencao_nota', 'Menção em Nota'),
        ('sistema_geral', 'Notificação do Sistema'),
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
    icone = models.CharField(
        max_length=50,
        default='fas fa-bell',
        verbose_name="Ícone",
        help_text="Classe FontAwesome (ex: fas fa-bell)"
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
        ('sistema', 'Sistema (in-app)'),
        ('email', 'Email'),
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
        unique_together = ('tenant', 'usuario', 'tipo_notificacao', 'canal_preferido')
        verbose_name = "Preferência de Notificação"
        verbose_name_plural = "⚙️ 03. Preferências de Notificação"
        ordering = ['usuario__username', 'tipo_notificacao__nome']

    def __str__(self):
        return f"{self.usuario.username} - {self.tipo_notificacao.nome}"


class Notificacao(TenantMixin):
    """Registro de notificações do sistema"""
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
    url_acao = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name="URL de Ação",
        help_text="Link ao clicar na notificação (ex: /comercial/leads/123/)"
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
    lida = models.BooleanField(
        default=False,
        verbose_name="Lida"
    )
    data_lida = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Leitura"
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

    # Integração externa (N8N, webhook, etc.)
    resposta_externa = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resposta Externa",
        help_text="Resposta da integração (N8N, webhook, etc.)"
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
            models.Index(fields=['destinatario', 'lida']),
        ]

    def __str__(self):
        return f"{self.tipo.nome} - {self.destinatario or self.destinatario_email}"

    @property
    def is_broadcast(self):
        """True quando a notif e broadcast (todos os usuarios do tenant veem)."""
        return self.destinatario_id is None


class NotificacaoLeituraBroadcast(models.Model):
    """
    Track de leitura de notificacoes broadcast (destinatario=NULL).

    Notificacoes pessoais usam Notificacao.lida direto. Broadcasts nao tem
    "uma" leitura — cada user que ve precisa ter seu proprio registro.
    """
    notificacao = models.ForeignKey(
        Notificacao,
        on_delete=models.CASCADE,
        related_name='leituras_broadcast',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='leituras_notif_broadcast',
    )
    data_leitura = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Leitura de notificacao broadcast'
        verbose_name_plural = 'Leituras de notificacao broadcast'
        constraints = [
            models.UniqueConstraint(
                fields=['notificacao', 'user'],
                name='unique_leitura_broadcast_por_user',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'notificacao']),
        ]

    def __str__(self):
        return f'{self.user} leu broadcast #{self.notificacao_id}'

    def marcar_lida(self):
        if not self.lida:
            self.lida = True
            self.data_lida = timezone.now()
            self.save(update_fields=['lida', 'data_lida'])


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
        unique_together = ('tenant', 'tipo_notificacao', 'canal')
        verbose_name = "Template de Notificação"
        verbose_name_plural = "📝 05. Templates de Notificação"
        ordering = ['tipo_notificacao__nome', 'canal__nome']

    def __str__(self):
        return f"{self.tipo_notificacao.nome} - {self.canal.nome}"
