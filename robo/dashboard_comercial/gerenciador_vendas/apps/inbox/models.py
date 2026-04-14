import uuid

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from apps.sistema.mixins import TenantMixin


class CanalInbox(TenantMixin):
    TIPO_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('widget', 'Chat Widget'),
        ('email', 'E-mail'),
        ('interno', 'Interno'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")
    nome = models.CharField(max_length=100, verbose_name="Nome")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    configuracao = models.JSONField(
        default=dict, blank=True, verbose_name="Configuração",
        help_text="URLs de webhook, tokens, etc. Ex: {webhook_envio_url: '...'}"
    )

    # Provider abstraction
    integracao = models.ForeignKey(
        'integracoes.IntegracaoAPI', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='canais', verbose_name="Integração",
        help_text="Integração de API vinculada a este canal",
    )
    provedor = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name="Provedor",
        help_text="Slug do provider: uazapi, evolution, meta_cloud, twilio, webhook",
    )
    identificador_canal = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Identificador",
        help_text="Número de telefone, ID da instância, etc.",
    )
    fluxo = models.ForeignKey(
        'atendimento.FluxoAtendimento', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='canais_inbox', verbose_name="Fluxo de Atendimento",
        help_text="Fluxo que será iniciado ao receber mensagem neste canal",
    )

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        db_table = 'inbox_canais'
        verbose_name = "Canal"
        verbose_name_plural = "Canais"
        unique_together = [['tenant', 'tipo', 'identificador_canal']]

    def __str__(self):
        extra = f" · {self.identificador_canal}" if self.identificador_canal else ''
        return f"{self.nome} ({self.get_tipo_display()}{extra})"


class EtiquetaConversa(TenantMixin):
    nome = models.CharField(max_length=50, verbose_name="Nome")
    cor_hex = models.CharField(max_length=7, default='#667eea', verbose_name="Cor")
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Criado por"
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        db_table = 'inbox_etiquetas'
        verbose_name = "Etiqueta"
        verbose_name_plural = "Etiquetas"
        unique_together = [['tenant', 'nome']]

    def __str__(self):
        return self.nome


class Conversa(TenantMixin):
    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('pendente', 'Pendente'),
        ('resolvida', 'Resolvida'),
        ('arquivada', 'Arquivada'),
    ]
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    MODO_ATENDIMENTO_CHOICES = [
        ('bot', 'Bot'),
        ('humano', 'Humano'),
        ('finalizado_bot', 'Finalizado pelo Bot'),
        ('assistente', 'Assistente CRM'),
    ]

    numero = models.PositiveIntegerField(verbose_name="Número", editable=False)
    canal = models.ForeignKey(
        CanalInbox, on_delete=models.PROTECT,
        related_name='conversas', verbose_name="Canal"
    )
    lead = models.ForeignKey(
        'leads.LeadProspecto', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversas', verbose_name="Lead"
    )
    contato_nome = models.CharField(max_length=255, blank=True, verbose_name="Nome do Contato")
    contato_telefone = models.CharField(max_length=17, blank=True, db_index=True, verbose_name="Telefone")
    contato_email = models.EmailField(blank=True, verbose_name="E-mail")

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aberta', verbose_name="Status")
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='normal', verbose_name="Prioridade")
    agente = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversas_atribuidas', verbose_name="Agente"
    )
    etiquetas = models.ManyToManyField(EtiquetaConversa, blank=True, verbose_name="Etiquetas")

    equipe = models.ForeignKey(
        'EquipeInbox', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversas', verbose_name="Equipe"
    )
    fila = models.ForeignKey(
        'FilaInbox', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversas', verbose_name="Fila"
    )
    ticket = models.ForeignKey(
        'suporte.Ticket', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversas', verbose_name="Ticket"
    )
    oportunidade = models.ForeignKey(
        'crm.OportunidadeVenda', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversas', verbose_name="Oportunidade"
    )

    identificador_externo = models.CharField(
        max_length=100, blank=True, db_index=True,
        verbose_name="ID Externo",
        help_text="Thread ID do WhatsApp ou referência externa"
    )
    ultima_mensagem_em = models.DateTimeField(null=True, blank=True, verbose_name="Última mensagem")
    ultima_mensagem_preview = models.CharField(max_length=255, blank=True, verbose_name="Preview")
    mensagens_nao_lidas = models.PositiveIntegerField(default=0, verbose_name="Não lidas")
    tempo_primeira_resposta_seg = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Tempo 1ª resposta (seg)"
    )

    modo_atendimento = models.CharField(
        max_length=20, choices=MODO_ATENDIMENTO_CHOICES,
        default='humano', verbose_name="Modo de Atendimento",
        help_text="bot = fluxo ativo, humano = transferido para atendente, finalizado_bot = bot encerrou"
    )

    data_abertura = models.DateTimeField(auto_now_add=True, verbose_name="Data de Abertura")
    data_resolucao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Resolução")
    data_arquivamento = models.DateTimeField(null=True, blank=True, verbose_name="Data de Arquivamento")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Metadata")

    class Meta:
        db_table = 'inbox_conversas'
        verbose_name = "Conversa"
        verbose_name_plural = "Conversas"
        ordering = ['-ultima_mensagem_em']
        unique_together = [['tenant', 'numero']]
        indexes = [
            models.Index(fields=['status', 'agente']),
            models.Index(fields=['canal', 'status']),
            models.Index(fields=['ultima_mensagem_em']),
            models.Index(fields=['contato_telefone']),
            models.Index(fields=['equipe', 'status']),
            models.Index(fields=['fila', 'status']),
        ]

    def __str__(self):
        nome = self.contato_nome or self.contato_telefone or f"#{self.numero}"
        return f"#{self.numero} {nome}"

    def save(self, *args, **kwargs):
        if not self.numero:
            from django.db.models import Max
            ultimo = Conversa.all_tenants.filter(tenant=self.tenant).aggregate(Max('numero'))
            self.numero = (ultimo['numero__max'] or 0) + 1
        super().save(*args, **kwargs)


class Mensagem(TenantMixin):
    REMETENTE_TIPO_CHOICES = [
        ('contato', 'Contato'),
        ('agente', 'Agente'),
        ('sistema', 'Sistema'),
        ('bot', 'Bot'),
    ]
    TIPO_CONTEUDO_CHOICES = [
        ('texto', 'Texto'),
        ('imagem', 'Imagem'),
        ('arquivo', 'Arquivo'),
        ('audio', 'Áudio'),
        ('video', 'Vídeo'),
        ('localizacao', 'Localização'),
        ('sistema', 'Mensagem de Sistema'),
    ]

    conversa = models.ForeignKey(
        Conversa, on_delete=models.CASCADE,
        related_name='mensagens', verbose_name="Conversa"
    )
    remetente_tipo = models.CharField(
        max_length=10, choices=REMETENTE_TIPO_CHOICES, verbose_name="Tipo do Remetente"
    )
    remetente_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Usuário Remetente"
    )
    remetente_nome = models.CharField(max_length=255, blank=True, verbose_name="Nome do Remetente")

    tipo_conteudo = models.CharField(
        max_length=15, choices=TIPO_CONTEUDO_CHOICES, default='texto',
        verbose_name="Tipo de Conteúdo"
    )
    conteudo = models.TextField(verbose_name="Conteúdo")
    arquivo_url = models.URLField(blank=True, verbose_name="URL do Arquivo")
    arquivo_nome = models.CharField(max_length=255, blank=True, verbose_name="Nome do Arquivo")
    arquivo_tamanho = models.PositiveIntegerField(null=True, blank=True, verbose_name="Tamanho (bytes)")

    lida = models.BooleanField(default=False, verbose_name="Lida")
    data_leitura = models.DateTimeField(null=True, blank=True, verbose_name="Data de Leitura")
    data_envio = models.DateTimeField(default=timezone.now, verbose_name="Data de Envio")
    data_entrega = models.DateTimeField(null=True, blank=True, verbose_name="Data de Entrega")
    identificador_externo = models.CharField(
        max_length=100, blank=True, db_index=True,
        verbose_name="ID Externo",
        help_text="Message ID do WhatsApp ou referência externa"
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Metadata")
    erro_envio = models.TextField(blank=True, verbose_name="Erro de Envio")

    class Meta:
        db_table = 'inbox_mensagens'
        verbose_name = "Mensagem"
        verbose_name_plural = "Mensagens"
        ordering = ['data_envio']
        indexes = [
            models.Index(fields=['conversa', 'data_envio']),
            models.Index(fields=['identificador_externo']),
        ]

    def __str__(self):
        preview = self.conteudo[:50] if self.conteudo else self.get_tipo_conteudo_display()
        return f"{self.get_remetente_tipo_display()}: {preview}"


class RespostaRapida(TenantMixin):
    titulo = models.CharField(max_length=100, verbose_name="Título")
    atalho = models.CharField(
        max_length=50, blank=True, verbose_name="Atalho",
        help_text="Comando rápido, ex: /saudacao"
    )
    conteudo = models.TextField(verbose_name="Conteúdo")
    categoria = models.CharField(max_length=50, blank=True, verbose_name="Categoria")
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Criado por"
    )
    uso_count = models.PositiveIntegerField(default=0, verbose_name="Vezes usado")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        db_table = 'inbox_respostas_rapidas'
        verbose_name = "Resposta Rápida"
        verbose_name_plural = "Respostas Rápidas"
        ordering = ['-uso_count']
        unique_together = [['tenant', 'atalho']]

    def __str__(self):
        return self.titulo


class NotaInternaConversa(TenantMixin):
    conversa = models.ForeignKey(
        Conversa, on_delete=models.CASCADE,
        related_name='notas_internas', verbose_name="Conversa"
    )
    autor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Autor")
    conteudo = models.TextField(verbose_name="Conteúdo")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data")

    class Meta:
        db_table = 'inbox_notas_internas'
        verbose_name = "Nota Interna"
        verbose_name_plural = "Notas Internas"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Nota #{self.conversa.numero} — {self.autor.username}"


# ═══════════════════════════════════════════════════════════════════════
# EQUIPES, FILAS E DISTRIBUIÇÃO
# ═══════════════════════════════════════════════════════════════════════

class EquipeInbox(TenantMixin):
    nome = models.CharField(max_length=100, verbose_name="Nome")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    cor_hex = models.CharField(max_length=7, default='#667eea', verbose_name="Cor")
    lider = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipes_inbox_lideradas', verbose_name="Líder"
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        db_table = 'inbox_equipes'
        verbose_name = "Equipe"
        verbose_name_plural = "Equipes"
        ordering = ['nome']
        unique_together = [['tenant', 'nome']]

    def __str__(self):
        return self.nome


class MembroEquipeInbox(TenantMixin):
    CARGO_CHOICES = [
        ('agente', 'Agente'),
        ('supervisor', 'Supervisor'),
        ('gerente', 'Gerente'),
    ]

    equipe = models.ForeignKey(
        EquipeInbox, on_delete=models.CASCADE,
        related_name='membros', verbose_name="Equipe"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='membros_equipe_inbox', verbose_name="Usuário"
    )
    cargo = models.CharField(max_length=20, choices=CARGO_CHOICES, default='agente', verbose_name="Cargo")
    adicionado_em = models.DateTimeField(auto_now_add=True, verbose_name="Adicionado em")

    class Meta:
        db_table = 'inbox_membros_equipe'
        verbose_name = "Membro de Equipe"
        verbose_name_plural = "Membros de Equipe"
        unique_together = [['equipe', 'user']]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.equipe.nome}"


class PerfilAgenteInbox(TenantMixin):
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('ausente', 'Ausente'),
        ('offline', 'Offline'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='perfil_inbox', verbose_name="Usuário"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='offline', verbose_name="Status")
    capacidade_maxima = models.PositiveIntegerField(
        default=10, verbose_name="Capacidade Máxima",
        help_text="Máximo de conversas abertas simultâneas"
    )
    ultimo_status_em = models.DateTimeField(auto_now=True, verbose_name="Último status em")

    class Meta:
        db_table = 'inbox_perfis_agente'
        verbose_name = "Perfil de Agente"
        verbose_name_plural = "Perfis de Agente"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_status_display()})"

    @property
    def conversas_abertas_count(self):
        return Conversa.all_tenants.filter(
            tenant=self.tenant,
            agente=self.user,
            status__in=['aberta', 'pendente'],
        ).count()

    @property
    def disponivel(self):
        return self.status == 'online' and self.conversas_abertas_count < self.capacidade_maxima


class FilaInbox(TenantMixin):
    MODO_DISTRIBUICAO_CHOICES = [
        ('round_robin', 'Round Robin'),
        ('menor_carga', 'Menor Carga'),
        ('manual', 'Manual'),
    ]

    nome = models.CharField(max_length=100, verbose_name="Nome")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    equipe = models.ForeignKey(
        EquipeInbox, on_delete=models.CASCADE,
        related_name='filas', verbose_name="Equipe"
    )
    prioridade = models.PositiveIntegerField(
        default=0, verbose_name="Prioridade",
        help_text="Maior = processada primeiro"
    )
    modo_distribuicao = models.CharField(
        max_length=15, choices=MODO_DISTRIBUICAO_CHOICES,
        default='round_robin', verbose_name="Modo de Distribuição"
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    ultimo_agente_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Último agente atribuído (para round-robin)"
    )
    mensagem_fora_horario = models.TextField(
        blank=True, default='',
        verbose_name="Mensagem fora do horário",
        help_text="Mensagem enviada automaticamente quando fora do horário da fila"
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        db_table = 'inbox_filas'
        verbose_name = "Fila"
        verbose_name_plural = "Filas"
        ordering = ['-prioridade', 'nome']
        unique_together = [['tenant', 'nome']]

    def __str__(self):
        return f"{self.nome} ({self.equipe.nome})"


class RegraRoteamento(TenantMixin):
    TIPO_CHOICES = [
        ('canal', 'Por Canal'),
        ('etiqueta', 'Por Etiqueta'),
        ('horario', 'Por Horário'),
    ]

    fila = models.ForeignKey(
        FilaInbox, on_delete=models.CASCADE,
        related_name='regras', verbose_name="Fila"
    )
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, verbose_name="Tipo")
    canal = models.ForeignKey(
        CanalInbox, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Canal", help_text="Quando tipo = Por Canal"
    )
    etiqueta = models.ForeignKey(
        EtiquetaConversa, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Etiqueta", help_text="Quando tipo = Por Etiqueta"
    )
    horario_inicio = models.TimeField(null=True, blank=True, verbose_name="Horário início")
    horario_fim = models.TimeField(null=True, blank=True, verbose_name="Horário fim")
    dias_semana = models.CharField(
        max_length=20, blank=True, verbose_name="Dias da semana",
        help_text="Separados por vírgula: 0=Seg, 1=Ter, ..., 6=Dom. Ex: 0,1,2,3,4"
    )
    prioridade = models.PositiveIntegerField(default=0, verbose_name="Prioridade")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        db_table = 'inbox_regras_roteamento'
        verbose_name = "Regra de Roteamento"
        verbose_name_plural = "Regras de Roteamento"
        ordering = ['-prioridade']

    def __str__(self):
        return f"{self.get_tipo_display()} → {self.fila.nome}"


class HistoricoTransferencia(TenantMixin):
    conversa = models.ForeignKey(
        Conversa, on_delete=models.CASCADE,
        related_name='transferencias', verbose_name="Conversa"
    )
    de_agente = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="De agente"
    )
    para_agente = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Para agente"
    )
    de_equipe = models.ForeignKey(
        EquipeInbox, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="De equipe"
    )
    para_equipe = models.ForeignKey(
        EquipeInbox, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Para equipe"
    )
    para_fila = models.ForeignKey(
        FilaInbox, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Para fila"
    )
    motivo = models.TextField(blank=True, verbose_name="Motivo")
    transferido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Transferido por"
    )
    data = models.DateTimeField(auto_now_add=True, verbose_name="Data")

    class Meta:
        db_table = 'inbox_historico_transferencia'
        verbose_name = "Transferência"
        verbose_name_plural = "Transferências"
        ordering = ['-data']

    def __str__(self):
        return f"Conversa #{self.conversa.numero} — {self.data}"


class HorarioAtendimento(TenantMixin):
    DIA_CHOICES = [
        (0, 'Segunda'), (1, 'Terça'), (2, 'Quarta'),
        (3, 'Quinta'), (4, 'Sexta'), (5, 'Sábado'), (6, 'Domingo'),
    ]

    fila = models.ForeignKey(
        FilaInbox, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='horarios', verbose_name="Fila",
        help_text="Se vazio, aplica como horario global (fallback)"
    )
    dia_semana = models.IntegerField(choices=DIA_CHOICES, verbose_name="Dia da Semana")
    hora_inicio = models.TimeField(verbose_name="Hora Início")
    hora_fim = models.TimeField(verbose_name="Hora Fim")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        db_table = 'inbox_horario_atendimento'
        verbose_name = "Horário de Atendimento"
        verbose_name_plural = "Horários de Atendimento"
        unique_together = [['tenant', 'fila', 'dia_semana']]
        ordering = ['dia_semana']

    def __str__(self):
        fila_nome = self.fila.nome if self.fila else 'Global'
        return f"[{fila_nome}] {self.get_dia_semana_display()}: {self.hora_inicio} - {self.hora_fim}"


class ConfiguracaoInbox(TenantMixin):
    mensagem_fora_horario = models.TextField(
        blank=True,
        default="Nosso horário de atendimento é de segunda a sexta, das 8h às 18h. Responderemos assim que possível.",
        verbose_name="Mensagem fora do horário"
    )
    distribuicao_padrao = models.CharField(
        max_length=15, choices=FilaInbox.MODO_DISTRIBUICAO_CHOICES,
        default='round_robin', verbose_name="Distribuição padrão"
    )
    atribuir_ao_responder = models.BooleanField(
        default=True, verbose_name="Atribuir ao responder",
        help_text="Auto-atribuir agente quando responde conversa sem agente"
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inbox_configuracao'
        verbose_name = "Configuração do Inbox"
        verbose_name_plural = "Configurações do Inbox"

    def __str__(self):
        return "Configuração do Inbox"

    @classmethod
    def get_config(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj


# ═══════════════════════════════════════════════════════════════════════
# FAQ / BASE DE CONHECIMENTO
# ═══════════════════════════════════════════════════════════════════════

class CategoriaFAQ(TenantMixin):
    nome = models.CharField(max_length=100, verbose_name="Nome")
    slug = models.SlugField(max_length=100, verbose_name="Slug")
    icone = models.CharField(max_length=50, blank=True, default='fa-circle-question', verbose_name="Ícone FontAwesome")
    cor = models.CharField(max_length=7, default='#667eea', verbose_name="Cor")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        db_table = 'inbox_faq_categorias'
        verbose_name = "Categoria FAQ"
        verbose_name_plural = "Categorias FAQ"
        ordering = ['ordem', 'nome']
        unique_together = [['tenant', 'slug']]

    def __str__(self):
        return self.nome


class ArtigoFAQ(TenantMixin):
    categoria = models.ForeignKey(
        CategoriaFAQ, on_delete=models.CASCADE,
        related_name='artigos', verbose_name="Categoria"
    )
    titulo = models.CharField(max_length=200, verbose_name="Título")
    conteudo = models.TextField(verbose_name="Conteúdo")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    visualizacoes = models.PositiveIntegerField(default=0, verbose_name="Visualizações")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        db_table = 'inbox_faq_artigos'
        verbose_name = "Artigo FAQ"
        verbose_name_plural = "Artigos FAQ"
        ordering = ['ordem', 'titulo']

    def __str__(self):
        return self.titulo


# ═══════════════════════════════════════════════════════════════════════
# WIDGET CONFIG
# ═══════════════════════════════════════════════════════════════════════

class WidgetConfig(TenantMixin):
    POSICAO_CHOICES = [
        ('bottom-right', 'Inferior Direito'),
        ('bottom-left', 'Inferior Esquerdo'),
    ]

    token_publico = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True,
        verbose_name="Token Público"
    )
    titulo = models.CharField(max_length=200, default="Como podemos ajudar?", verbose_name="Título")
    mensagem_boas_vindas = models.CharField(max_length=500, default="Olá 👋", verbose_name="Mensagem de Boas Vindas")
    cor_primaria = models.CharField(max_length=7, default='#3b82f6', verbose_name="Cor Primária")
    cor_header = models.CharField(max_length=7, default='#1e3a5f', verbose_name="Cor do Header")
    posicao = models.CharField(max_length=15, choices=POSICAO_CHOICES, default='bottom-right', verbose_name="Posição")
    mostrar_faq = models.BooleanField(default=True, verbose_name="Mostrar FAQ")
    pedir_dados_antes = models.BooleanField(
        default=True, verbose_name="Pedir dados antes",
        help_text="Solicitar nome/email antes de permitir chat"
    )
    campos_obrigatorios = models.JSONField(
        default=list, blank=True, verbose_name="Campos Obrigatórios",
        help_text="Lista de campos: nome, email, telefone"
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    dominios_permitidos = models.JSONField(
        default=list, blank=True, verbose_name="Domínios Permitidos",
        help_text="Lista de domínios. Vazio = todos permitidos."
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        db_table = 'inbox_widget_config'
        verbose_name = "Configuração do Widget"
        verbose_name_plural = "Configurações do Widget"

    def __str__(self):
        return f"Widget {self.tenant} ({self.token_publico})"

    @classmethod
    def get_config(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create(campos_obrigatorios=['nome', 'email'])
        return obj

    @classmethod
    def get_by_token(cls, token):
        try:
            return cls.all_tenants.select_related('tenant').get(
                token_publico=token, ativo=True
            )
        except (cls.DoesNotExist, ValueError):
            return None
