"""
Comando — operação interna da Hubtrix (mono-tenant).

Os 11 models abaixo são camada de IA herdada do megaroleta legado.
NÃO usam TenantMixin: são singleton da operação Hubtrix, igual aurora-admin.

Status: DORMENTE na fase 1 — apenas schema + dados importados.
Sem views, sem URLs, sem templates, sem sidebar entry.
Acesso: Django admin (read-only) + python manage.py shell.

Quando ressuscitar (fase 3):
- Decidir se permanece mono-tenant ou se vira multi-tenant
- Reescrever ai_service e agent_actions adaptado
- Possível redesenho de prompts pro contexto SaaS
"""
from django.db import models


# ============================================================================
# AGENTES & TOOLS
# ============================================================================

class Agente(models.Model):
    TIME_CHOICES = [
        ('executivo', 'Executivo'),
        ('marketing', 'Marketing'),
        ('sucesso', 'Sucesso do Cliente'),
        ('parcerias', 'Parcerias'),
        ('tech', 'Tech'),
    ]

    slug = models.SlugField(unique=True, max_length=100)
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    icone = models.CharField(max_length=50, default='bi-robot')
    cor = models.CharField(max_length=7, default='#252020')
    time = models.CharField(max_length=20, choices=TIME_CHOICES, default='executivo')
    prompt = models.TextField(blank=True, help_text="Prompt principal do agente em modo chat")
    prompt_autonomo = models.TextField(blank=True, help_text="Prompt em modo autônomo (vazio = usa o principal)")
    modelo = models.CharField(max_length=50, default='gpt-4o-mini')
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_agente'
        verbose_name = 'Agente'
        verbose_name_plural = 'Agentes'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class ToolAgente(models.Model):
    TIPO_CHOICES = [
        ('executavel', 'Executável'),
        ('conhecimento', 'Conhecimento'),
    ]

    slug = models.SlugField(unique=True, max_length=100)
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    icone = models.CharField(max_length=50, default='bi-tools')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='executavel')
    prompt = models.TextField(blank=True)
    exemplo = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_tool_agente'
        verbose_name = 'Tool de Agente'
        verbose_name_plural = 'Tools de Agentes'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class LogTool(models.Model):
    """Log unificado de execução de tools (sem truncagem)."""
    tool = models.ForeignKey(ToolAgente, null=True, blank=True, on_delete=models.SET_NULL, related_name='logs')
    agente = models.ForeignKey(Agente, null=True, blank=True, on_delete=models.SET_NULL, related_name='logs_tools')
    tool_slug = models.CharField(max_length=100, db_index=True)
    resultado = models.TextField(blank=True)
    sucesso = models.BooleanField(default=True)
    tempo_ms = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_log_tool'
        verbose_name = 'Log de Tool'
        verbose_name_plural = 'Logs de Tools'
        ordering = ['-criado_em']

    def __str__(self):
        status = 'OK' if self.sucesso else 'ERRO'
        return f"[{status}] {self.tool_slug} ({self.tempo_ms}ms)"


class MensagemChat(models.Model):
    """Mensagem em chat 1:1 com agente."""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    agente = models.ForeignKey(Agente, on_delete=models.CASCADE, related_name='mensagens_chat')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_mensagem_chat'
        verbose_name = 'Mensagem de Chat'
        verbose_name_plural = 'Mensagens de Chat'
        ordering = ['criado_em']

    def __str__(self):
        return f"{self.role}: {self.conteudo[:50]}"


# ============================================================================
# REUNIÕES MULTI-AGENTE
# ============================================================================

class Reuniao(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    agentes = models.TextField(blank=True, help_text="CSV de IDs de agentes participantes")
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_reuniao'
        verbose_name = 'Reunião'
        verbose_name_plural = 'Reuniões'
        ordering = ['-criado_em']

    def __str__(self):
        return self.nome

    @property
    def agentes_lista(self):
        if not self.agentes:
            return []
        return [int(x.strip()) for x in self.agentes.split(',') if x.strip().isdigit()]

    @property
    def total_mensagens(self):
        return self.mensagens.count()


class MensagemReuniao(models.Model):
    TIPO_CHOICES = [
        ('ceo', 'CEO'),
        ('agente', 'Agente'),
        ('moderador', 'Moderador'),
    ]

    reuniao = models.ForeignKey(Reuniao, on_delete=models.CASCADE, related_name='mensagens')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    agente_id = models.IntegerField(null=True, blank=True, help_text="ID solto do Agente que falou")
    agente_nome = models.CharField(max_length=200, blank=True)
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_mensagem_reuniao'
        verbose_name = 'Mensagem de Reunião'
        verbose_name_plural = 'Mensagens de Reunião'
        ordering = ['criado_em']

    def __str__(self):
        return f"[{self.tipo}] {self.agente_nome or '-'}: {self.conteudo[:50]}"


# ============================================================================
# AUTOMAÇÕES + ALERTAS + PROPOSTAS
# ============================================================================

class Automacao(models.Model):
    MODO_CHOICES = [
        ('tool', 'Tool'),
        ('agente', 'Agente'),
    ]
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('pausado', 'Pausado'),
        ('erro', 'Erro'),
    ]

    modo = models.CharField(max_length=20, choices=MODO_CHOICES, default='tool')
    tool = models.ForeignKey(ToolAgente, null=True, blank=True, on_delete=models.SET_NULL, related_name='automacoes')
    agente = models.ForeignKey(Agente, null=True, blank=True, on_delete=models.SET_NULL, related_name='automacoes')
    encaminhar_para = models.ForeignKey(
        Agente, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='automacoes_recebidas',
        help_text="Agente que recebe o resultado pra análise",
    )
    intervalo_horas = models.PositiveIntegerField(default=24)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pausado')
    ultima_execucao = models.DateTimeField(null=True, blank=True)
    ultimo_resultado = models.TextField(blank=True)
    ultima_analise = models.TextField(blank=True)
    total_execucoes = models.PositiveIntegerField(default=0)
    total_erros = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=False, help_text="Default False na fase 1 — não roda")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_automacao'
        verbose_name = 'Automação'
        verbose_name_plural = 'Automações'
        ordering = ['-criado_em']

    def __str__(self):
        alvo = self.tool.nome if self.tool else (self.agente.nome if self.agente else '-')
        return f"[{self.modo}] {alvo} ({self.intervalo_horas}h)"


class Alerta(models.Model):
    SEVERIDADE_CHOICES = [
        ('info', 'Info'),
        ('aviso', 'Aviso'),
        ('critico', 'Crítico'),
    ]
    TIPO_CHOICES = [
        ('health', 'Health'),
        ('estoque', 'Estoque'),
        ('churn', 'Churn'),
        ('metrica', 'Métrica'),
        ('erro', 'Erro'),
        ('outro', 'Outro'),
    ]

    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, default='outro')
    severidade = models.CharField(max_length=20, choices=SEVERIDADE_CHOICES, default='info')
    titulo = models.CharField(max_length=300)
    descricao = models.TextField(blank=True)
    dados_json = models.JSONField(default=dict, blank=True)
    agente = models.ForeignKey(Agente, null=True, blank=True, on_delete=models.SET_NULL, related_name='alertas')
    tool = models.ForeignKey(ToolAgente, null=True, blank=True, on_delete=models.SET_NULL, related_name='alertas')
    lido = models.BooleanField(default=False)
    resolvido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_alerta'
        verbose_name = 'Alerta'
        verbose_name_plural = 'Alertas'
        ordering = ['-criado_em']

    def __str__(self):
        return f"[{self.severidade}] {self.titulo}"


class Proposta(models.Model):
    PRIORIDADE_CHOICES = [
        ('critica', 'Crítica'),
        ('alta', 'Alta'),
        ('media', 'Média'),
        ('baixa', 'Baixa'),
    ]
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('aprovada', 'Aprovada'),
        ('rejeitada', 'Rejeitada'),
        ('executada', 'Executada'),
        ('erro', 'Erro'),
    ]

    agente = models.ForeignKey(Agente, on_delete=models.CASCADE, related_name='propostas')
    tool = models.ForeignKey(ToolAgente, null=True, blank=True, on_delete=models.SET_NULL, related_name='propostas')
    alerta = models.ForeignKey(Alerta, null=True, blank=True, on_delete=models.SET_NULL, related_name='propostas')
    reuniao = models.ForeignKey(Reuniao, null=True, blank=True, on_delete=models.SET_NULL, related_name='propostas')
    titulo = models.CharField(max_length=300)
    descricao = models.TextField()
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default='media')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    dados_execucao = models.JSONField(default=dict, blank=True)
    motivo_rejeicao = models.TextField(blank=True)
    resultado_execucao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    data_decisao = models.DateTimeField(null=True, blank=True)
    data_execucao = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_proposta'
        verbose_name = 'Proposta'
        verbose_name_plural = 'Propostas'
        ordering = ['-criado_em']

    def __str__(self):
        return f"[{self.status}] {self.titulo}"


# ============================================================================
# FAQ GERADO POR IA
# ============================================================================

class FAQCategoria(models.Model):
    nome = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    icone = models.CharField(max_length=50, default='bi-question-circle')
    cor = models.CharField(max_length=7, default='#252020')
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_faq_categoria'
        verbose_name = 'Categoria de FAQ'
        verbose_name_plural = 'Categorias de FAQ'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class FAQItem(models.Model):
    categoria = models.ForeignKey(FAQCategoria, on_delete=models.CASCADE, related_name='itens')
    pergunta = models.TextField()
    resposta = models.TextField()
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    gerado_por_ia = models.BooleanField(default=False)
    hash_dados_fonte = models.CharField(max_length=64, blank=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'comando'
        db_table = 'comando_faq_item'
        verbose_name = 'Item de FAQ'
        verbose_name_plural = 'Itens de FAQ'
        ordering = ['categoria', 'ordem']

    def __str__(self):
        return self.pergunta[:80]
