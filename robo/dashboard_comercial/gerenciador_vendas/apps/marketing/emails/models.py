import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.sistema.mixins import TenantMixin


# ============================================================================
# CATEGORIA DE TEMPLATE
# ============================================================================

class CategoriaTemplate(TenantMixin):
    """Categoria para organizar templates de email."""

    nome = models.CharField(max_length=100)
    icone = models.CharField(
        max_length=50, default='fas fa-folder',
        help_text='Classe FontAwesome (ex: fas fa-envelope)'
    )
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'marketing_categoria_template'
        verbose_name = 'Categoria de Template'
        verbose_name_plural = 'Categorias de Templates'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


# ============================================================================
# TEMPLATE DE EMAIL
# ============================================================================

class TemplateEmail(TenantMixin):
    """Template de email construído pelo editor visual de blocos."""

    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('ativo', 'Ativo'),
        ('arquivado', 'Arquivado'),
    ]

    # Identificação
    nome = models.CharField(max_length=200, help_text='Nome interno do template')
    descricao = models.TextField(blank=True, help_text='Descrição opcional')
    assunto = models.CharField(
        max_length=300, blank=True,
        help_text='Assunto do email. Suporta variáveis: {{lead.nome}}'
    )

    # Conteúdo visual
    config_json = models.JSONField(
        default=dict, blank=True,
        help_text='Configurações globais do email (largura, cores, fonte)'
    )
    blocos_json = models.JSONField(
        default=list, blank=True,
        help_text='Lista de blocos do editor visual'
    )
    html_compilado = models.TextField(
        blank=True,
        help_text='HTML renderizado a partir dos blocos (gerado automaticamente)'
    )

    # Organização
    categoria = models.ForeignKey(
        CategoriaTemplate, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='templates'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rascunho', db_index=True)
    eh_modelo_base = models.BooleanField(
        default=False,
        help_text='Templates base do sistema (disponíveis para todos os tenants)'
    )

    # Thumbnail
    thumbnail = models.ImageField(
        upload_to='emails/thumbnails/', blank=True, null=True,
        help_text='Preview em miniatura do template'
    )

    # Metadata
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='templates_email_criados'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketing_template_email'
        verbose_name = 'Template de Email'
        verbose_name_plural = 'Templates de Email'
        ordering = ['-atualizado_em']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['eh_modelo_base']),
        ]

    def __str__(self):
        return self.nome

    @property
    def total_blocos(self):
        if isinstance(self.blocos_json, list):
            return len(self.blocos_json)
        return 0

    @property
    def total_envios(self):
        return self.envios.count()


# ============================================================================
# ENVIO DE EMAIL
# ============================================================================

class EnvioEmail(TenantMixin):
    """Registro de cada email enviado."""

    STATUS_CHOICES = [
        ('enviado', 'Enviado'),
        ('aberto', 'Aberto'),
        ('clicado', 'Clicado'),
        ('erro', 'Erro'),
        ('bounce', 'Bounce'),
    ]

    template = models.ForeignKey(
        TemplateEmail, on_delete=models.SET_NULL,
        null=True, related_name='envios'
    )
    lead = models.ForeignKey(
        'leads.LeadProspecto', on_delete=models.SET_NULL,
        null=True, related_name='emails_recebidos'
    )
    automacao = models.ForeignKey(
        'automacoes.RegraAutomacao', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='emails_enviados'
    )

    # Dados do envio
    email_destino = models.EmailField()
    assunto_renderizado = models.CharField(max_length=300)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='enviado', db_index=True)

    # Tracking
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    enviado_em = models.DateTimeField(auto_now_add=True)
    aberto_em = models.DateTimeField(null=True, blank=True)
    clicado_em = models.DateTimeField(null=True, blank=True)

    # Erro
    erro_detalhe = models.TextField(blank=True)

    class Meta:
        db_table = 'marketing_envio_email'
        verbose_name = 'Envio de Email'
        verbose_name_plural = 'Envios de Email'
        ordering = ['-enviado_em']
        indexes = [
            models.Index(fields=['tracking_id']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.email_destino} — {self.assunto_renderizado[:50]}'

    def registrar_abertura(self):
        if not self.aberto_em:
            self.aberto_em = timezone.now()
            if self.status == 'enviado':
                self.status = 'aberto'
            self.save(update_fields=['aberto_em', 'status'])

    def registrar_clique(self):
        if not self.clicado_em:
            self.clicado_em = timezone.now()
            self.status = 'clicado'
            self.save(update_fields=['clicado_em', 'status'])
        if not self.aberto_em:
            self.registrar_abertura()
