import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.sistema.mixins import TenantMixin


# ============================================================================
# DOMINIO DE REMETENTE — autenticado via DNS no provedor master (Resend)
# ============================================================================

class DominioRemetente(TenantMixin):
    """
    Dominio de envio do tenant, autenticado no Resend via DNS (SPF/DKIM/DMARC).
    Tenant pode ter multiplos. Apenas dominios verificados podem enviar email.
    """
    STATUS_CHOICES = [
        ('pendente_dns',   'Pendente — adicionar DNS'),
        ('validando',      'Validando DNS'),
        ('verificado',     'Verificado'),
        ('falhou',         'Falhou'),
        ('desabilitado',   'Desabilitado'),
    ]

    dominio = models.CharField(
        max_length=255,
        help_text='Ex: meuprovedor.com.br',
    )
    nome_amigavel = models.CharField(
        max_length=100, blank=True,
        help_text='Apelido pra organizar quando o tenant tem varios dominios',
    )

    # Integracao Resend
    resend_domain_id = models.CharField(
        max_length=100, blank=True, db_index=True,
        help_text='ID retornado pela API Resend ao criar o dominio',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pendente_dns',
        db_index=True,
    )
    registros_dns = models.JSONField(
        default=list, blank=True,
        help_text='3 registros DNS (SPF/DKIM/DMARC) que o tenant precisa adicionar',
    )

    # Validacao
    validado_em = models.DateTimeField(null=True, blank=True)
    falha_motivo = models.TextField(blank=True)
    ultima_verificacao = models.DateTimeField(null=True, blank=True)

    # Flags de comportamento
    capturar_bounces = models.BooleanField(
        default=True,
        help_text='Salvar info de bounce nos envios deste dominio',
    )
    capturar_complaints = models.BooleanField(
        default=True,
        help_text='Salvar info de complaint (spam) nos envios deste dominio',
    )
    auto_remover_lista = models.BooleanField(
        default=False,
        help_text='Remover automaticamente da lista quando bate bounce/complaint',
    )

    # Metadata
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketing_dominio_remetente'
        verbose_name = 'Dominio de Remetente'
        verbose_name_plural = 'Dominios de Remetente'
        ordering = ['-criado_em']
        unique_together = [['tenant', 'dominio']]

    def __str__(self):
        return self.dominio

    @property
    def esta_verificado(self):
        return self.status == 'verificado'

    @property
    def total_remetentes(self):
        return self.remetentes.filter(ativo=True).count()


# ============================================================================
# REMETENTE — endereco especifico dentro de um dominio (ex: atendimento@)
# ============================================================================

class RemetenteEmail(TenantMixin):
    """
    Endereco de envio dentro de um dominio verificado.
    Ex: 'atendimento@meuprovedor.com.br' com nome 'Atendimento Hubtrix'.
    """
    dominio = models.ForeignKey(
        DominioRemetente, on_delete=models.CASCADE,
        related_name='remetentes',
    )
    local_part = models.CharField(
        max_length=64,
        help_text='Parte antes do @ (ex: atendimento, marketing, noreply)',
    )
    nome_exibicao = models.CharField(
        max_length=200,
        help_text='Nome que aparece como remetente (ex: Atendimento Hubtrix)',
    )
    reply_to = models.EmailField(
        blank=True,
        help_text='Endereco pra onde respostas vao. Vazio = ignorar.',
    )
    padrao = models.BooleanField(
        default=False,
        help_text='Remetente padrao do tenant (apenas 1 ativo)',
    )
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marketing_remetente_email'
        verbose_name = 'Remetente de Email'
        verbose_name_plural = 'Remetentes de Email'
        ordering = ['dominio', 'local_part']
        unique_together = [['dominio', 'local_part']]

    def __str__(self):
        return f'{self.nome_exibicao} <{self.email_completo}>'

    @property
    def email_completo(self):
        return f'{self.local_part}@{self.dominio.dominio}'

    def save(self, *args, **kwargs):
        # Garantir apenas 1 remetente padrao por tenant
        if self.padrao:
            RemetenteEmail.all_tenants.filter(
                tenant=self.tenant, padrao=True
            ).exclude(pk=self.pk).update(padrao=False)
        super().save(*args, **kwargs)


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
        ('pendente', 'Pendente'),
        ('enviado', 'Enviado'),
        ('entregue', 'Entregue'),
        ('aberto', 'Aberto'),
        ('clicado', 'Clicado'),
        ('erro', 'Erro'),
        ('bounce', 'Bounce'),
        ('complained', 'Marcado como spam'),
    ]

    template = models.ForeignKey(
        TemplateEmail, on_delete=models.SET_NULL,
        null=True, related_name='envios'
    )
    remetente = models.ForeignKey(
        RemetenteEmail, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='envios',
        help_text='Endereco usado pra enviar (vazio = remetente padrao do tenant na epoca)',
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

    # Tracking interno (pixel) — mantido pra retrocompat
    tracking_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Tracking via provedor (Resend)
    resend_message_id = models.CharField(
        max_length=200, blank=True, db_index=True,
        help_text='ID retornado pelo Resend (correlaciona webhooks)',
    )

    # Datas de evento
    enviado_em = models.DateTimeField(auto_now_add=True)
    entregue_em = models.DateTimeField(null=True, blank=True)
    aberto_em = models.DateTimeField(null=True, blank=True)
    clicado_em = models.DateTimeField(null=True, blank=True)

    # Erros e bounces
    erro_detalhe = models.TextField(blank=True)
    bounce_type = models.CharField(
        max_length=50, blank=True,
        help_text='hard / soft / undetermined (do provedor)',
    )
    complaint_type = models.CharField(max_length=50, blank=True)

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
