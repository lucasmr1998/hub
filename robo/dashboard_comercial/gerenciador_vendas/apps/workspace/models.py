"""
Workspace — gestão de projetos, tarefas e documentos.

Multi-tenant: todos os models herdam TenantMixin.
Campos preparados pra IA estão presentes mas dormentes na fase 1.
FK pra comando.Agente é opcional e fica nula até a fase de IA.
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.sistema.mixins import TenantMixin


# ============================================================================
# CHOICES COMUNS
# ============================================================================

PRIORIDADE_CHOICES = [
    ('baixa', 'Baixa'),
    ('media', 'Média'),
    ('alta', 'Alta'),
    ('critica', 'Crítica'),
]

PROJETO_STATUS_CHOICES = [
    ('planejamento', 'Planejamento'),
    ('em_andamento', 'Em andamento'),
    ('pausado', 'Pausado'),
    ('concluido', 'Concluído'),
    ('cancelado', 'Cancelado'),
]

TAREFA_STATUS_CHOICES = [
    ('rascunho', 'Rascunho'),
    ('pendente', 'Pendente'),
    ('em_andamento', 'Em andamento'),
    ('concluida', 'Concluída'),
    ('bloqueada', 'Bloqueada'),
]

DOCUMENTO_FORMATO_CHOICES = [
    ('markdown', 'Markdown'),
    ('html', 'HTML'),
    ('imagem', 'Imagem'),
    ('pdf', 'PDF'),
    ('link', 'Link externo'),
]

DOCUMENTO_CATEGORIA_CHOICES = [
    ('estrategia', 'Estratégia'),
    ('regras', 'Regras'),
    ('roadmap', 'Roadmap'),
    ('decisoes', 'Decisões'),
    ('entrega', 'Entrega'),
    ('sessao', 'Sessão'),
    ('contexto', 'Contexto'),
    ('relatorio', 'Relatório'),
    ('email', 'Email'),
    ('processo', 'Processo'),
    ('imagem', 'Imagem'),
    ('outro', 'Outro'),
]


# ============================================================================
# PROJETO
# ============================================================================

class Projeto(TenantMixin):
    nome = models.CharField(max_length=200, verbose_name='Nome')
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    status = models.CharField(max_length=20, choices=PROJETO_STATUS_CHOICES, default='planejamento')
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default='media')

    # Campos estratégicos
    objetivo = models.TextField(blank=True, verbose_name='Objetivo')
    publico_alvo = models.TextField(blank=True, verbose_name='Público-alvo')
    criterios_sucesso = models.TextField(blank=True, verbose_name='Critérios de sucesso')
    riscos = models.TextField(blank=True, verbose_name='Riscos')
    premissas = models.TextField(blank=True, verbose_name='Premissas')

    # Pessoas
    responsavel = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='projetos_responsavel', verbose_name='Responsável',
    )
    stakeholders = models.TextField(blank=True, verbose_name='Stakeholders',
        help_text='Texto livre por enquanto')

    # Datas e orçamento
    data_inicio = models.DateField(null=True, blank=True)
    data_fim_prevista = models.DateField(null=True, blank=True)
    orcamento = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Preparado pra IA — dormente na fase 1
    contexto_agentes = models.TextField(blank=True,
        help_text='Briefing pra agentes IA usarem quando trabalharem no projeto')

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'workspace'
        db_table = 'workspace_projeto'
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'ativo']),
        ]

    def __str__(self):
        return self.nome

    def total_tarefas(self):
        return self.tarefas.count()

    def total_concluidas(self):
        return self.tarefas.filter(status='concluida').count()

    def progresso(self):
        total = getattr(self, 'n_tarefas', None)
        concluidas = getattr(self, 'n_concluidas', None)
        if total is None:
            total = self.total_tarefas()
            concluidas = self.total_concluidas()
        if not total:
            return 0
        return int((concluidas / total) * 100)


# ============================================================================
# ETAPA
# ============================================================================

class Etapa(TenantMixin):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='etapas')
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0)
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'workspace'
        db_table = 'workspace_etapa'
        verbose_name = 'Etapa'
        verbose_name_plural = 'Etapas'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.projeto.nome} — {self.nome}'

    def total_tarefas(self):
        return self.tarefas.count()

    def total_concluidas(self):
        return self.tarefas.filter(status='concluida').count()


# ============================================================================
# DOCUMENTO + PASTA
# ============================================================================

def documento_upload_path(instance, filename):
    """Path: workspace/docs/<tenant_id>/<slug>/<filename>"""
    tenant_id = instance.tenant_id or 0
    slug = instance.slug or 'sem-slug'
    return f'workspace/docs/{tenant_id}/{slug}/{filename}'


class PastaDocumento(TenantMixin):
    nome = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    icone = models.CharField(max_length=50, default='bi-folder',
        help_text='Bootstrap Icons (bi-*)')
    cor = models.CharField(max_length=7, default='#252020',
        help_text='Hex color — paleta v2 (tinta default)')
    ordem = models.PositiveIntegerField(default=0)
    pai = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='subpastas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'workspace'
        db_table = 'workspace_pasta_documento'
        verbose_name = 'Pasta de Documento'
        verbose_name_plural = 'Pastas de Documentos'
        ordering = ['ordem', 'nome']
        unique_together = [['tenant', 'slug']]

    def __str__(self):
        return self.nome

    def total_documentos(self):
        """Total de docs nesta pasta + todas subpastas recursivamente."""
        n = self.documentos.count()
        for sub in self.subpastas.all():
            n += sub.total_documentos()
        return n

    def total_subpastas(self):
        """Total de subpastas (apenas filhas diretas)."""
        return self.subpastas.count()


class Documento(TenantMixin):
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    categoria = models.CharField(max_length=20, choices=DOCUMENTO_CATEGORIA_CHOICES, default='outro')
    formato = models.CharField(
        max_length=20, choices=DOCUMENTO_FORMATO_CHOICES, default='markdown',
        help_text='Como o conteúdo deve ser renderizado',
    )
    conteudo = models.TextField(blank=True, help_text='Markdown ou HTML, conforme o formato')
    arquivo = models.FileField(upload_to=documento_upload_path, null=True, blank=True)
    resumo = models.TextField(blank=True)
    descricao = models.TextField(blank=True)
    url_externa = models.URLField(blank=True, help_text='Para formato=link')

    # Preparado pra IA
    visivel_agentes = models.BooleanField(default=True)
    agente_origem = models.ForeignKey(
        'comando.Agente', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='documentos_criados',
        help_text='Agente que gerou esse documento (se gerado por IA)',
    )

    pasta = models.ForeignKey(
        PastaDocumento, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='documentos',
    )
    ordem = models.PositiveIntegerField(default=0)

    criado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='documentos_criados', verbose_name='Criado por',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'workspace'
        db_table = 'workspace_documento'
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        ordering = ['-atualizado_em']
        unique_together = [['tenant', 'slug']]
        indexes = [
            models.Index(fields=['tenant', 'categoria']),
            models.Index(fields=['tenant', 'pasta']),
        ]

    def __str__(self):
        return self.titulo


# ============================================================================
# TAREFA + NOTA
# ============================================================================

class Tarefa(TenantMixin):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='tarefas')
    etapa = models.ForeignKey(Etapa, null=True, blank=True, on_delete=models.SET_NULL, related_name='tarefas')

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tarefas_responsavel',
    )
    status = models.CharField(max_length=20, choices=TAREFA_STATUS_CHOICES, default='pendente')
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default='media')
    data_limite = models.DateField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    ordem = models.PositiveIntegerField(default=0, help_text='Pra kanban drag-and-drop')

    # Preparado pra IA — dormente na fase 1
    objetivo = models.TextField(blank=True)
    contexto = models.TextField(blank=True)
    passos = models.TextField(blank=True)
    entregavel = models.TextField(blank=True)
    criterios_aceite = models.TextField(blank=True)
    log_execucao = models.TextField(blank=True)
    nivel_delegacao = models.PositiveSmallIntegerField(default=0,
        help_text='0=humano, 1-2=agente IA')
    documento_processo = models.ForeignKey(
        Documento, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tarefas_processo',
        help_text='SOP/processo associado',
    )
    criado_por_agente = models.ForeignKey(
        'comando.Agente', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tarefas_criadas',
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'workspace'
        db_table = 'workspace_tarefa'
        verbose_name = 'Tarefa'
        verbose_name_plural = 'Tarefas'
        ordering = ['ordem', '-criado_em']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'responsavel']),
            models.Index(fields=['projeto', 'status', 'ordem']),
        ]

    def __str__(self):
        return self.titulo

    def registrar_log(self, mensagem):
        """Append ao log de execução com timestamp."""
        ts = timezone.now().strftime('%d/%m/%Y %H:%M')
        nova = f'[{ts}] {mensagem}'
        self.log_execucao = f'{self.log_execucao}\n{nova}' if self.log_execucao else nova
        self.save(update_fields=['log_execucao', 'atualizado_em'])

    def marcar_concluida(self):
        self.status = 'concluida'
        self.data_conclusao = timezone.now()
        self.save(update_fields=['status', 'data_conclusao', 'atualizado_em'])


class Nota(TenantMixin):
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name='notas')
    texto = models.TextField()
    autor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='notas_workspace',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'workspace'
        db_table = 'workspace_nota'
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'
        ordering = ['criado_em']

    def __str__(self):
        return self.texto[:80]


# ============================================================================
# ANEXO DE DOCUMENTO — multiplos arquivos por documento (imagens, PDFs, etc.)
# ============================================================================

def anexo_upload_path(instance, filename):
    tenant_id = instance.tenant_id or 0
    doc_slug = instance.documento.slug if instance.documento_id else 'sem-doc'
    return f'workspace/anexos/{tenant_id}/{doc_slug}/{filename}'


class AnexoDocumento(TenantMixin):
    """Arquivo anexado a um documento (imagem, PDF, etc.)."""
    TIPO_CHOICES = [
        ('imagem', 'Imagem'),
        ('arquivo', 'Arquivo'),
    ]

    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE, related_name='anexos',
    )
    arquivo = models.FileField(upload_to=anexo_upload_path)
    nome_original = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='arquivo')
    mime_type = models.CharField(max_length=100, blank=True)
    tamanho_bytes = models.PositiveBigIntegerField(default=0)

    # Metadata de geracao IA (se aplicavel)
    gerado_por_ia = models.BooleanField(default=False)
    prompt_ia = models.TextField(blank=True)
    modelo_ia = models.CharField(max_length=100, blank=True)

    criado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='anexos_workspace',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'workspace'
        db_table = 'workspace_anexo_documento'
        verbose_name = 'Anexo de Documento'
        verbose_name_plural = 'Anexos de Documentos'
        ordering = ['-criado_em']

    def __str__(self):
        return self.nome_original or self.arquivo.name

    @property
    def eh_imagem(self):
        return self.tipo == 'imagem' or (self.mime_type or '').startswith('image/')
