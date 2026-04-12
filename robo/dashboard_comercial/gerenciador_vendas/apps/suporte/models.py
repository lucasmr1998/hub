from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from apps.sistema.mixins import TenantMixin


class CategoriaTicket(TenantMixin):
    nome = models.CharField(max_length=100, verbose_name="Nome")
    slug = models.SlugField(verbose_name="Slug")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    icone = models.CharField(max_length=50, default='fa-tag', verbose_name="Ícone FontAwesome")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    fila_padrao = models.ForeignKey(
        'inbox.FilaInbox', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='categorias_ticket',
        verbose_name="Fila Padrao",
        help_text="Tickets desta categoria serao atribuidos automaticamente a esta fila"
    )

    class Meta:
        db_table = 'suporte_categorias'
        verbose_name = "Categoria de Ticket"
        verbose_name_plural = "Categorias de Ticket"
        ordering = ['ordem']
        unique_together = [['tenant', 'slug']]

    def __str__(self):
        return self.nome


class SLAConfig(TenantMixin):
    PLANO_CHOICES = [
        ('starter', 'Starter'),
        ('start', 'Start'),
        ('pro', 'Pro'),
    ]

    plano_tier = models.CharField(max_length=10, choices=PLANO_CHOICES, verbose_name="Plano")
    tempo_primeira_resposta_horas = models.PositiveIntegerField(verbose_name="SLA Primeira Resposta (horas)")
    tempo_resolucao_horas = models.PositiveIntegerField(verbose_name="SLA Resolução (horas)")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        db_table = 'suporte_sla_config'
        verbose_name = "Configuração de SLA"
        verbose_name_plural = "Configurações de SLA"
        unique_together = [['tenant', 'plano_tier']]

    def __str__(self):
        return f"SLA {self.get_plano_tier_display()}: {self.tempo_primeira_resposta_horas}h resposta, {self.tempo_resolucao_horas}h resolução"


class Ticket(TenantMixin):
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    STATUS_CHOICES = [
        ('aberto', 'Aberto'),
        ('em_andamento', 'Em Andamento'),
        ('aguardando_cliente', 'Aguardando Cliente'),
        ('resolvido', 'Resolvido'),
        ('fechado', 'Fechado'),
    ]

    numero = models.PositiveIntegerField(verbose_name="Número", editable=False)
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descricao = models.TextField(verbose_name="Descrição")
    categoria = models.ForeignKey(
        CategoriaTicket, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tickets', verbose_name="Categoria"
    )
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='normal', verbose_name="Prioridade")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aberto', verbose_name="Status")

    solicitante = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='tickets_abertos', verbose_name="Solicitante"
    )
    atendente = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tickets_atribuidos', verbose_name="Atendente"
    )
    tenant_cliente = models.ForeignKey(
        'sistema.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tickets_suporte', verbose_name="Tenant Cliente",
        help_text="Qual provedor abriu este ticket"
    )

    sla_horas = models.PositiveIntegerField(null=True, blank=True, verbose_name="SLA (horas)")

    # CSAT (Customer Satisfaction)
    csat_nota = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Nota CSAT",
        help_text="1 a 5 estrelas"
    )
    csat_comentario = models.TextField(blank=True, default='', verbose_name="Comentario CSAT")
    csat_data = models.DateTimeField(null=True, blank=True, verbose_name="Data CSAT")

    data_abertura = models.DateTimeField(auto_now_add=True, verbose_name="Data de Abertura")
    data_primeira_resposta = models.DateTimeField(null=True, blank=True, verbose_name="Primeira Resposta")
    data_resolucao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Resolução")
    data_fechamento = models.DateTimeField(null=True, blank=True, verbose_name="Data de Fechamento")

    class Meta:
        db_table = 'suporte_tickets'
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ['-data_abertura']
        indexes = [
            models.Index(fields=['status', 'prioridade']),
            models.Index(fields=['atendente', 'status']),
            models.Index(fields=['tenant_cliente']),
        ]
        unique_together = [['tenant', 'numero']]

    def __str__(self):
        return f"#{self.numero} {self.titulo}"

    @property
    def sla_cumprido(self):
        if not self.sla_horas:
            return True
        referencia = self.data_resolucao or timezone.now()
        horas = (referencia - self.data_abertura).total_seconds() / 3600
        return horas <= self.sla_horas

    def save(self, *args, **kwargs):
        if not self.numero:
            from django.db.models import Max
            ultimo = Ticket.all_tenants.filter(tenant=self.tenant).aggregate(Max('numero'))
            self.numero = (ultimo['numero__max'] or 0) + 1

        if not self.sla_horas and self.tenant_cliente:
            tier = getattr(self.tenant_cliente, 'plano_comercial', 'starter')
            sla = SLAConfig.all_tenants.filter(tenant=self.tenant, plano_tier=tier).first()
            if sla:
                self.sla_horas = sla.tempo_resolucao_horas

        super().save(*args, **kwargs)


class ComentarioTicket(TenantMixin):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE,
        related_name='comentarios', verbose_name="Ticket"
    )
    autor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Autor")
    mensagem = models.TextField(verbose_name="Mensagem")
    interno = models.BooleanField(
        default=False, verbose_name="Comentário Interno",
        help_text="Visível apenas para a equipe de suporte"
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data")

    class Meta:
        db_table = 'suporte_comentarios'
        verbose_name = "Comentário"
        verbose_name_plural = "Comentários"
        ordering = ['data_criacao']

    def __str__(self):
        return f"#{self.ticket.numero} — {self.autor.username}"


class HistoricoTicket(TenantMixin):
    """Registra mudancas no ticket (status, atribuicao, prioridade, etc)."""
    TIPO_CHOICES = [
        ('status', 'Mudanca de Status'),
        ('atribuicao', 'Atribuicao'),
        ('prioridade', 'Mudanca de Prioridade'),
        ('categoria', 'Mudanca de Categoria'),
        ('comentario', 'Comentario'),
        ('criacao', 'Criacao'),
        ('sla', 'SLA'),
        ('escalacao', 'Escalacao'),
    ]

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE,
        related_name='historico', verbose_name="Ticket"
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario"
    )
    campo = models.CharField(max_length=50, blank=True, verbose_name="Campo alterado")
    valor_anterior = models.CharField(max_length=200, blank=True, verbose_name="Valor anterior")
    valor_novo = models.CharField(max_length=200, blank=True, verbose_name="Valor novo")
    descricao = models.CharField(max_length=255, blank=True, verbose_name="Descricao")
    data = models.DateTimeField(auto_now_add=True, verbose_name="Data")

    class Meta:
        db_table = 'suporte_historico_ticket'
        verbose_name = "Historico do Ticket"
        verbose_name_plural = "Historico de Tickets"
        ordering = ['-data']

    def __str__(self):
        return f"#{self.ticket.numero} — {self.get_tipo_display()} ({self.data})"


# ============================================================================
# BASE DE CONHECIMENTO — artigos internos para agentes
# ============================================================================

class CategoriaConhecimento(TenantMixin):
    """Categoria de artigos da base de conhecimento interna."""
    nome = models.CharField(max_length=100, verbose_name="Nome")
    slug = models.SlugField(verbose_name="Slug")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    icone = models.CharField(max_length=50, default='fa-book', verbose_name="Ícone FA")
    cor_hex = models.CharField(max_length=7, default='#3b82f6', verbose_name="Cor")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        db_table = 'suporte_categorias_conhecimento'
        verbose_name = "Categoria (Base de Conhecimento)"
        verbose_name_plural = "Categorias (Base de Conhecimento)"
        ordering = ['ordem', 'nome']
        unique_together = [['tenant', 'slug']]

    def __str__(self):
        return self.nome

    @property
    def total_artigos(self):
        return self.artigos_conhecimento.filter(publicado=True).count()


class ArtigoConhecimento(TenantMixin):
    """Artigo da base de conhecimento interna (para agentes)."""
    categoria = models.ForeignKey(
        CategoriaConhecimento, on_delete=models.CASCADE,
        related_name='artigos_conhecimento', verbose_name="Categoria",
    )
    titulo = models.CharField(max_length=255, verbose_name="Título")
    slug = models.SlugField(max_length=255, verbose_name="Slug")
    conteudo = models.TextField(verbose_name="Conteúdo",
        help_text="Suporta Markdown para formatação")
    resumo = models.CharField(max_length=300, blank=True, verbose_name="Resumo",
        help_text="Resumo curto exibido na listagem")
    tags = models.CharField(max_length=500, blank=True, verbose_name="Tags",
        help_text="Separadas por vírgula (ex: roteador, instalacao, fibra)")
    publicado = models.BooleanField(default=True, verbose_name="Publicado")
    destaque = models.BooleanField(default=False, verbose_name="Destaque",
        help_text="Aparece em destaque no topo da base")
    autor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='artigos_conhecimento', verbose_name="Autor",
    )
    visualizacoes = models.PositiveIntegerField(default=0, verbose_name="Visualizações")
    util_sim = models.PositiveIntegerField(default=0, verbose_name="Útil: Sim")
    util_nao = models.PositiveIntegerField(default=0, verbose_name="Útil: Não")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        db_table = 'suporte_artigos_conhecimento'
        verbose_name = "Artigo (Base de Conhecimento)"
        verbose_name_plural = "Artigos (Base de Conhecimento)"
        ordering = ['-destaque', '-atualizado_em']
        unique_together = [['tenant', 'slug']]

    def __str__(self):
        return self.titulo

    @property
    def tags_lista(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]


# ============================================================================
# PERGUNTAS SEM RESPOSTA (Base de Conhecimento IA)
# ============================================================================

class PerguntaSemResposta(TenantMixin):
    """Pergunta feita ao Agente IA que não encontrou resposta na base de conhecimento."""
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('respondida', 'Respondida'),
        ('ignorada', 'Ignorada'),
    ]

    pergunta = models.TextField(verbose_name="Pergunta")
    lead = models.ForeignKey(
        'leads.LeadProspecto', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='perguntas_sem_resposta',
        verbose_name="Lead"
    )
    conversa = models.ForeignKey(
        'inbox.Conversa', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Conversa"
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pendente',
        verbose_name="Status"
    )
    ocorrencias = models.PositiveIntegerField(
        default=1, verbose_name="Ocorrências",
        help_text="Quantas vezes essa pergunta (ou similar) foi feita"
    )
    artigo_criado = models.ForeignKey(
        ArtigoConhecimento, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='perguntas_origem',
        verbose_name="Artigo Criado"
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    data_resposta = models.DateTimeField(
        null=True, blank=True, verbose_name="Respondido em"
    )

    class Meta:
        db_table = 'suporte_perguntas_sem_resposta'
        verbose_name = "Pergunta sem Resposta"
        verbose_name_plural = "❓ Perguntas sem Resposta"
        ordering = ['-ocorrencias', '-data_criacao']

    def __str__(self):
        return f"{self.pergunta[:80]}... ({self.get_status_display()})"
