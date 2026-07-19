from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ============================================================================
# PIPELINE
# ============================================================================

class PipelineEstagio(models.Model):
    TIPO_CHOICES = [
        ('novo', 'Novo Lead'),
        ('qualificacao', 'Qualificação'),
        ('negociacao', 'Negociação'),
        ('fechamento', 'Fechamento'),
        ('cliente', 'Cliente Ativo'),
        ('retencao', 'Retenção'),
        ('perdido', 'Perdido'),
    ]

    # Em qual pipeline (tipo de oportunidade) este estágio aparece.
    # Alinha o CRM aos fluxos reais: aquisição de lead novo, e o pós-venda
    # do cliente existente (novo serviço, upgrade, atendimento).
    PIPELINE_TIPO_CHOICES = [
        ('aquisicao',    'Aquisição (lead novo → cliente)'),
        ('novo_servico', 'Novo Serviço (cliente existente)'),
        ('upgrade',      'Upgrade de Plano'),
        ('atendimento',  'Atendimento / Suporte'),
        ('indicacao',    'Indicação (operado por pessoas)'),
        ('wifeed',       'Wifeed (portal WiFi)'),
    ]

    nome = models.CharField(max_length=100, verbose_name="Nome")
    slug = models.SlugField(unique=True, verbose_name="Slug")
    pipeline_tipo = models.CharField(
        max_length=20, choices=PIPELINE_TIPO_CHOICES, default='aquisicao',
        db_index=True, verbose_name="Pipeline",
    )
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")
    cor_hex = models.CharField(max_length=7, default='#667eea', verbose_name="Cor (HEX)")
    icone_fa = models.CharField(max_length=50, default='fa-circle', verbose_name="Ícone FontAwesome")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='novo', verbose_name="Tipo")
    is_final_ganho = models.BooleanField(default=False, verbose_name="Estágio de Ganho")
    is_final_perdido = models.BooleanField(default=False, verbose_name="Estágio de Perda")
    probabilidade_padrao = models.IntegerField(default=50, verbose_name="Probabilidade Padrão (%)")
    sla_horas = models.PositiveIntegerField(null=True, blank=True, verbose_name="SLA (horas)")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crm_pipeline_estagios'
        verbose_name = "Estágio do Pipeline"
        verbose_name_plural = "🏷️ 01. Estágios do Pipeline"
        ordering = ['ordem']

    def __str__(self):
        return self.nome


class RegraPipelineEstagio(models.Model):
    """
    Regra configurável para movimentação automática de oportunidades.
    Cada regra contém condições AND; múltiplas regras por estágio usam OR.
    Estágios avaliados por ordem; primeiro match ganha.
    """
    TIPO_CONDICAO_CHOICES = [
        ('historico_status', 'Status do Histórico de Contato'),
        ('lead_status_api', 'Status API do Lead'),
        ('lead_campo', 'Campo do Lead'),
        ('servico_status', 'Status do Serviço Hubsoft'),
        ('tag', 'Tag CRM'),
        ('converteu_venda', 'Converteu em Venda'),
    ]

    OPERADOR_CHOICES = [
        ('igual', 'Igual a'),
        ('diferente', 'Diferente de'),
        ('existe', 'Existe / Verdadeiro'),
        ('nao_existe', 'Não existe / Falso'),
    ]

    estagio = models.ForeignKey(
        PipelineEstagio,
        on_delete=models.CASCADE,
        related_name='regras',
        verbose_name="Estágio",
    )
    nome = models.CharField(
        max_length=150,
        verbose_name="Nome da Regra",
        help_text="Descrição curta (ex: 'Serviço habilitado + doc validada')",
    )
    condicoes = models.JSONField(
        default=list,
        verbose_name="Condições",
        help_text="Lista de condições AND: [{tipo, campo, operador, valor}, ...]",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativa")
    prioridade = models.PositiveIntegerField(
        default=0,
        verbose_name="Prioridade",
        help_text="Menor valor = avaliada primeiro dentro do estágio",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_regras_pipeline_estagio'
        verbose_name = "Regra de Pipeline"
        verbose_name_plural = "Regras de Pipeline"
        ordering = ['estagio__ordem', 'prioridade']

    def __str__(self):
        return f"{self.estagio.nome} — {self.nome}"


# ============================================================================
# EQUIPE E PERFIL
# ============================================================================

class EquipeVendas(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome da Equipe")
    lider = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipes_lideradas', verbose_name="Líder"
    )
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    cor_hex = models.CharField(max_length=7, default='#667eea', verbose_name="Cor (HEX)")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crm_equipes'
        verbose_name = "Equipe de Vendas"
        verbose_name_plural = "👥 02. Equipes de Vendas"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class PerfilVendedor(models.Model):
    CARGO_CHOICES = [
        ('vendedor', 'Vendedor'),
        ('supervisor', 'Supervisor'),
        ('gerente', 'Gerente Comercial'),
        ('diretor', 'Diretor'),
        ('outro', 'Outro'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_crm', verbose_name="Usuário")
    equipe = models.ForeignKey(
        EquipeVendas, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='membros', verbose_name="Equipe"
    )
    cargo = models.CharField(max_length=20, choices=CARGO_CHOICES, default='vendedor', verbose_name="Cargo")
    telefone_direto = models.CharField(max_length=20, blank=True, verbose_name="Telefone Direto")
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name="WhatsApp")
    id_vendedor_hubsoft = models.IntegerField(null=True, blank=True, verbose_name="ID Vendedor Hubsoft")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_admissao = models.DateField(null=True, blank=True, verbose_name="Data de Admissão")
    foto_url = models.URLField(null=True, blank=True, verbose_name="Foto URL")

    class Meta:
        db_table = 'crm_perfis_vendedor'
        verbose_name = "Perfil de Vendedor"
        verbose_name_plural = "👤 03. Perfis de Vendedor"
        ordering = ['user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_cargo_display()})"


# ============================================================================
# TAGS
# ============================================================================

class TagCRM(models.Model):
    nome = models.CharField(max_length=50, unique=True, verbose_name="Nome")
    cor_hex = models.CharField(max_length=7, default='#667eea', verbose_name="Cor (HEX)")
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crm_tags'
        verbose_name = "Tag CRM"
        verbose_name_plural = "🏷️ 04. Tags CRM"
        ordering = ['nome']

    def __str__(self):
        return self.nome


# ============================================================================
# OPORTUNIDADE (central do CRM)
# ============================================================================

class OportunidadeVenda(models.Model):
    ORIGEM_CHOICES = [
        ('automatico', 'Automático (Lead Qualificado)'),
        ('manual', 'Criação Manual'),
        ('importacao', 'Importação'),
    ]
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    # Tipo da oportunidade = qual pipeline ela percorre. Um cliente pode ter
    # várias: 1 de aquisição + N de novo serviço/upgrade/atendimento ao longo
    # do tempo. Por isso `lead` é ForeignKey (não mais OneToOne).
    TIPO_CHOICES = [
        ('aquisicao',    'Aquisição'),
        ('novo_servico', 'Novo Serviço'),
        ('upgrade',      'Upgrade de Plano'),
        ('atendimento',  'Atendimento'),
        ('indicacao',    'Indicação'),
        ('wifeed',       'Wifeed'),
    ]

    lead = models.ForeignKey(
        'vendas_web.LeadProspecto',
        on_delete=models.CASCADE,
        related_name='oportunidades_crm',
        verbose_name="Lead"
    )
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, default='aquisicao',
        db_index=True, verbose_name="Tipo / Pipeline",
    )
    # Vínculo com o objeto de origem do pós-venda (preenchido nos signals).
    new_service = models.ForeignKey(
        'vendas_web.NewService', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oportunidades_crm', verbose_name="Novo Serviço (origem)",
    )
    upgrade_plano = models.ForeignKey(
        'vendas_web.UpgradePlano', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oportunidades_crm', verbose_name="Upgrade (origem)",
    )
    estagio = models.ForeignKey(
        PipelineEstagio,
        on_delete=models.PROTECT,
        related_name='oportunidades',
        verbose_name="Estágio"
    )
    responsavel = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oportunidades_responsavel', verbose_name="Responsável"
    )
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oportunidades_criadas', verbose_name="Criado por"
    )

    titulo = models.CharField(max_length=255, blank=True, verbose_name="Título")
    valor_estimado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Valor Estimado (R$)")
    probabilidade = models.IntegerField(default=50, verbose_name="Probabilidade (%)")
    data_fechamento_previsto = models.DateField(null=True, blank=True, verbose_name="Previsão de Fechamento")
    data_fechamento_real = models.DateTimeField(null=True, blank=True, verbose_name="Data de Fechamento Real")

    plano_interesse = models.ForeignKey(
        'vendas_web.PlanoInternet', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oportunidades', verbose_name="Plano de Interesse"
    )

    origem_crm = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default='automatico', verbose_name="Origem no CRM")
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='normal', verbose_name="Prioridade")
    tags = models.ManyToManyField(TagCRM, blank=True, related_name='oportunidades', verbose_name="Tags")

    data_entrada_estagio = models.DateTimeField(default=timezone.now, verbose_name="Entrada no Estágio Atual")
    motivo_perda = models.TextField(null=True, blank=True, verbose_name="Motivo da Perda")
    concorrente_perdido = models.CharField(max_length=100, null=True, blank=True, verbose_name="Concorrente (Perda)")
    contrato_hubsoft_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID Contrato Hubsoft")
    churn_risk_score = models.IntegerField(null=True, blank=True, verbose_name="Score de Churn (0-100)")

    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        db_table = 'crm_oportunidades'
        verbose_name = "Oportunidade de Venda"
        verbose_name_plural = "💼 05. Oportunidades de Venda"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['estagio', 'ativo']),
            models.Index(fields=['responsavel', 'estagio']),
            models.Index(fields=['data_fechamento_previsto']),
            models.Index(fields=['churn_risk_score']),
        ]

    def __str__(self):
        nome = (self.lead.nome_razaosocial if self.lead else None) or self.titulo
        return f"{nome} — {self.estagio.nome}"

    @property
    def dias_no_estagio(self):
        delta = timezone.now() - self.data_entrada_estagio
        return delta.days

    @property
    def sla_vencido(self):
        if self.estagio.sla_horas:
            horas = (timezone.now() - self.data_entrada_estagio).total_seconds() / 3600
            return horas > self.estagio.sla_horas
        return False


class HistoricoPipelineEstagio(models.Model):
    oportunidade = models.ForeignKey(
        OportunidadeVenda, on_delete=models.CASCADE,
        related_name='historico_estagios', verbose_name="Oportunidade"
    )
    estagio_anterior = models.ForeignKey(
        PipelineEstagio, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Estágio Anterior"
    )
    estagio_novo = models.ForeignKey(
        PipelineEstagio, on_delete=models.PROTECT,
        related_name='+', verbose_name="Estágio Novo"
    )
    movido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Movido por")
    motivo = models.TextField(blank=True, verbose_name="Motivo")
    tempo_no_estagio_horas = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Tempo no Estágio (h)")
    data_transicao = models.DateTimeField(auto_now_add=True, verbose_name="Data da Transição")

    class Meta:
        db_table = 'crm_historico_estagio'
        verbose_name = "Histórico de Estágio"
        verbose_name_plural = "📋 06. Histórico de Estágios"
        ordering = ['-data_transicao']

    def __str__(self):
        anterior = self.estagio_anterior.nome if self.estagio_anterior else "—"
        return f"{self.oportunidade} | {anterior} → {self.estagio_novo.nome}"


# ============================================================================
# TAREFAS E NOTAS
# ============================================================================

class TarefaCRM(models.Model):
    TIPO_CHOICES = [
        ('ligacao', 'Ligação'),
        ('whatsapp', 'WhatsApp'),
        ('email', 'E-mail'),
        ('visita', 'Visita'),
        ('followup', 'Follow-up'),
        ('proposta', 'Proposta'),
        ('instalacao', 'Instalação'),
        ('suporte', 'Suporte'),
        ('outro', 'Outro'),
    ]
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('em_andamento', 'Em Andamento'),
        ('concluida', 'Concluída'),
        ('cancelada', 'Cancelada'),
        ('vencida', 'Vencida'),
    ]
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('normal', 'Normal'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]

    oportunidade = models.ForeignKey(
        OportunidadeVenda, on_delete=models.CASCADE, null=True, blank=True,
        related_name='tarefas', verbose_name="Oportunidade"
    )
    lead = models.ForeignKey(
        'vendas_web.LeadProspecto', on_delete=models.CASCADE, null=True, blank=True,
        related_name='tarefas_crm', verbose_name="Lead"
    )
    responsavel = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='tarefas_atribuidas', verbose_name="Responsável"
    )
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tarefas_criadas', verbose_name="Criado por"
    )

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='followup', verbose_name="Tipo")
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status")
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='normal', verbose_name="Prioridade")

    data_vencimento = models.DateTimeField(null=True, blank=True, verbose_name="Vencimento")
    data_conclusao = models.DateTimeField(null=True, blank=True, verbose_name="Concluída em")
    resultado = models.TextField(blank=True, verbose_name="Resultado")
    lembrete_em = models.DateTimeField(null=True, blank=True, verbose_name="Lembrete em")
    notificacao_enviada = models.BooleanField(default=False, verbose_name="Notificação Enviada")

    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_tarefas'
        verbose_name = "Tarefa CRM"
        verbose_name_plural = "✅ 07. Tarefas CRM"
        ordering = ['data_vencimento', '-prioridade']
        indexes = [
            models.Index(fields=['responsavel', 'status']),
            models.Index(fields=['data_vencimento', 'status']),
            models.Index(fields=['oportunidade']),
        ]

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.titulo}"

    def save(self, *args, **kwargs):
        # Marca como vencida automaticamente se passou do prazo
        if self.data_vencimento and self.status == 'pendente':
            if timezone.now() > self.data_vencimento:
                self.status = 'vencida'
        super().save(*args, **kwargs)


class NotaInterna(models.Model):
    TIPO_CHOICES = [
        ('geral', 'Geral'),
        ('reuniao', 'Reunião'),
        ('ligacao', 'Ligação'),
        ('email', 'E-mail'),
        ('importante', 'Importante'),
        ('alerta', 'Alerta'),
    ]

    oportunidade = models.ForeignKey(
        OportunidadeVenda, on_delete=models.CASCADE, null=True, blank=True,
        related_name='notas', verbose_name="Oportunidade"
    )
    lead = models.ForeignKey(
        'vendas_web.LeadProspecto', on_delete=models.CASCADE, null=True, blank=True,
        related_name='notas_crm', verbose_name="Lead"
    )
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notas_crm', verbose_name="Autor")
    mencoes = models.ManyToManyField(User, blank=True, related_name='mencoes_notas', verbose_name="Menções")

    conteudo = models.TextField(verbose_name="Conteúdo")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='geral', verbose_name="Tipo")
    is_fixada = models.BooleanField(default=False, verbose_name="Fixada")

    data_criacao = models.DateTimeField(auto_now_add=True)
    data_edicao = models.DateTimeField(null=True, blank=True)
    editado = models.BooleanField(default=False)

    class Meta:
        db_table = 'crm_notas_internas'
        verbose_name = "Nota Interna"
        verbose_name_plural = "📝 08. Notas Internas"
        ordering = ['-is_fixada', '-data_criacao']

    def __str__(self):
        return f"Nota de {self.autor.username} — {self.data_criacao.strftime('%d/%m/%Y')}"


# ============================================================================
# METAS
# ============================================================================

class MetaVendas(models.Model):
    TIPO_CHOICES = [
        ('individual', 'Individual'),
        ('equipe', 'Equipe'),
    ]
    PERIODO_CHOICES = [
        ('diario', 'Diário'),
        ('semanal', 'Semanal'),
        ('mensal', 'Mensal'),
        ('trimestral', 'Trimestral'),
    ]

    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='individual', verbose_name="Tipo")
    vendedor = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='metas_vendas', verbose_name="Vendedor"
    )
    equipe = models.ForeignKey(
        EquipeVendas, on_delete=models.CASCADE, null=True, blank=True,
        related_name='metas', verbose_name="Equipe"
    )
    periodo = models.CharField(max_length=15, choices=PERIODO_CHOICES, default='mensal', verbose_name="Período")
    data_inicio = models.DateField(verbose_name="Data Início")
    data_fim = models.DateField(verbose_name="Data Fim")

    meta_vendas_quantidade = models.PositiveIntegerField(default=0, verbose_name="Meta: Qtd. Vendas")
    meta_vendas_valor = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Meta: Valor (R$)")
    meta_leads_qualificados = models.PositiveIntegerField(default=0, verbose_name="Meta: Leads Qualificados")
    meta_contatos = models.PositiveIntegerField(default=0, verbose_name="Meta: Contatos")

    realizado_vendas_quantidade = models.PositiveIntegerField(default=0, verbose_name="Realizado: Qtd. Vendas")
    realizado_vendas_valor = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Realizado: Valor (R$)")
    realizado_leads = models.PositiveIntegerField(default=0, verbose_name="Realizado: Leads")

    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='metas_criadas')
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crm_metas_vendas'
        verbose_name = "Meta de Vendas"
        verbose_name_plural = "🎯 09. Metas de Vendas"
        ordering = ['-data_inicio']

    def __str__(self):
        alvo = self.vendedor.get_full_name() if self.vendedor else (self.equipe.nome if self.equipe else '—')
        return f"Meta {self.get_periodo_display()} — {alvo} ({self.data_inicio})"

    @property
    def percentual_quantidade(self):
        if self.meta_vendas_quantidade:
            return round((self.realizado_vendas_quantidade / self.meta_vendas_quantidade) * 100, 1)
        return 0

    @property
    def percentual_valor(self):
        if self.meta_vendas_valor:
            return round((float(self.realizado_vendas_valor) / float(self.meta_vendas_valor)) * 100, 1)
        return 0


# ============================================================================
# SEGMENTOS
# ============================================================================

class SegmentoCRM(models.Model):
    TIPO_CHOICES = [
        ('dinamico', 'Dinâmico'),
        ('manual', 'Manual'),
        ('hibrido', 'Híbrido'),
    ]

    nome = models.CharField(max_length=100, verbose_name="Nome")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='manual', verbose_name="Tipo")
    regras_filtro = models.JSONField(default=dict, blank=True, verbose_name="Regras de Filtro (JSON)")
    leads = models.ManyToManyField(
        'vendas_web.LeadProspecto', through='MembroSegmento',
        blank=True, related_name='segmentos_crm', verbose_name="Leads"
    )
    cor_hex = models.CharField(max_length=7, default='#764ba2', verbose_name="Cor (HEX)")
    icone_fa = models.CharField(max_length=50, default='fa-users', verbose_name="Ícone")
    ultima_atualizacao_dinamica = models.DateTimeField(null=True, blank=True)
    total_leads = models.PositiveIntegerField(default=0, verbose_name="Total de Leads")
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crm_segmentos'
        verbose_name = "Segmento CRM"
        verbose_name_plural = "🎯 10. Segmentos CRM"
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.total_leads} leads)"


class MembroSegmento(models.Model):
    segmento = models.ForeignKey(SegmentoCRM, on_delete=models.CASCADE, related_name='membros')
    lead = models.ForeignKey('vendas_web.LeadProspecto', on_delete=models.CASCADE, related_name='membros_segmento')
    adicionado_manualmente = models.BooleanField(default=False)
    adicionado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    data_adicao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crm_membros_segmento'
        unique_together = [['segmento', 'lead']]
        verbose_name = "Membro do Segmento"
        verbose_name_plural = "Membros de Segmento"


# ============================================================================
# RETENCAO
# ============================================================================

class AlertaRetencao(models.Model):
    TIPO_CHOICES = [
        ('contrato_expirando', 'Contrato Expirando'),
        ('inadimplencia', 'Inadimplência'),
        ('plano_downgradado', 'Plano Downgradado'),
        ('sem_uso', 'Sem Uso'),
        ('reclamacao', 'Reclamação'),
        ('upgrade_disponivel', 'Upgrade Disponível'),
        ('aniversario_contrato', 'Aniversário de Contrato'),
    ]
    NIVEL_CHOICES = [
        ('baixo', 'Baixo'),
        ('medio', 'Médio'),
        ('alto', 'Alto'),
        ('critico', 'Crítico'),
    ]
    STATUS_CHOICES = [
        ('novo', 'Novo'),
        ('em_tratamento', 'Em Tratamento'),
        ('resolvido', 'Resolvido'),
        ('perdido', 'Perdido'),
    ]

    cliente_hubsoft = models.ForeignKey(
        'integracoes.ClienteHubsoft', on_delete=models.CASCADE,
        related_name='alertas_retencao', verbose_name="Cliente Hubsoft"
    )
    lead = models.ForeignKey(
        'vendas_web.LeadProspecto', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alertas_retencao', verbose_name="Lead"
    )
    oportunidade = models.ForeignKey(
        OportunidadeVenda, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alertas_retencao', verbose_name="Oportunidade"
    )
    responsavel = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alertas_retencao', verbose_name="Responsável"
    )

    tipo_alerta = models.CharField(max_length=30, choices=TIPO_CHOICES, verbose_name="Tipo de Alerta")
    nivel_risco = models.CharField(max_length=10, choices=NIVEL_CHOICES, default='medio', verbose_name="Nível de Risco")
    score_churn = models.IntegerField(default=0, verbose_name="Score de Churn (0-100)")
    descricao = models.TextField(verbose_name="Descrição")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='novo', verbose_name="Status")

    data_expiracao_contrato = models.DateField(null=True, blank=True, verbose_name="Expiração do Contrato")
    data_detectado = models.DateTimeField(auto_now_add=True, verbose_name="Detectado em")
    data_resolucao = models.DateTimeField(null=True, blank=True, verbose_name="Resolvido em")
    acoes_tomadas = models.TextField(blank=True, verbose_name="Ações Tomadas")

    class Meta:
        db_table = 'crm_alertas_retencao'
        verbose_name = "Alerta de Retenção"
        verbose_name_plural = "🔔 11. Alertas de Retenção"
        ordering = ['-score_churn', '-data_detectado']

    def __str__(self):
        return f"{self.get_tipo_alerta_display()} — {self.cliente_hubsoft.nome_razaosocial} [{self.get_nivel_risco_display()}]"


# ============================================================================
# CONFIGURACAO (singleton)
# ============================================================================

class ConfiguracaoCRM(models.Model):
    sla_alerta_horas_padrao = models.PositiveIntegerField(default=48, verbose_name="SLA Padrão (horas)")
    criar_oportunidade_automatico = models.BooleanField(default=True, verbose_name="Criar Oportunidade Automaticamente")
    score_minimo_auto_criacao = models.IntegerField(default=7, verbose_name="Score Mínimo para Auto-Criação")
    estagio_inicial_padrao = models.ForeignKey(
        PipelineEstagio, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Estágio Inicial Padrão"
    )
    notificar_responsavel_nova_oportunidade = models.BooleanField(default=True)
    notificar_sla_breach = models.BooleanField(default=True)
    webhook_n8n_nova_oportunidade = models.URLField(null=True, blank=True, verbose_name="Webhook N8N: Nova Oportunidade")
    webhook_n8n_mudanca_estagio = models.URLField(null=True, blank=True, verbose_name="Webhook N8N: Mudança de Estágio")
    webhook_n8n_tarefa_vencida = models.URLField(null=True, blank=True, verbose_name="Webhook N8N: Tarefa Vencida")
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_configuracao'
        verbose_name = "Configuração do CRM"
        verbose_name_plural = "⚙️ 12. Configuração do CRM"

    def __str__(self):
        return "Configuração do CRM"

    @classmethod
    def get_config(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class MensagemPipeline(models.Model):
    """Mensagem inicial de WhatsApp por pipeline (usada ao clicar no botão do lead).

    Configurável na tela de admin. Suporta os placeholders {nome} e {primeiro_nome},
    substituídos pelos dados do lead ao abrir o WhatsApp.
    """
    pipeline_tipo = models.CharField(
        max_length=20, unique=True,
        choices=PipelineEstagio.PIPELINE_TIPO_CHOICES,
        verbose_name='Pipeline')
    mensagem = models.TextField(blank=True, default='', verbose_name='Mensagem inicial')
    ativo = models.BooleanField(default=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mensagem_pipeline'
        verbose_name = 'Mensagem de WhatsApp do Pipeline'
        verbose_name_plural = 'Mensagens de WhatsApp dos Pipelines'

    def __str__(self):
        return f'Mensagem WhatsApp — {self.get_pipeline_tipo_display()}'


class WifeedFonte(models.Model):
    """Fonte de leads do Wifeed (portal WiFi) selecionável no painel.

    Catálogo de LOCAIS e CAMPANHAS espelhado da API Wifeed. Quando `ativo=True`,
    o poller (wifeed_sync_leads) puxa leads dessa fonte:
      - local    → GET /report/record?local=<externo_id>
      - campanha → GET /report/access?campaign=<externo_id>
    """
    TIPO_CHOICES = [
        ('local', 'Local (ponto WiFi)'),
        ('campanha', 'Campanha'),
    ]
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, db_index=True, verbose_name='Tipo')
    externo_id = models.BigIntegerField(verbose_name='ID no Wifeed')
    nome = models.CharField(max_length=200, blank=True, default='', verbose_name='Nome')
    ativo = models.BooleanField(default=False, db_index=True,
                                verbose_name='Traz leads?',
                                help_text='Se marcado, o poller cria leads desta fonte.')
    ativo_wifeed = models.BooleanField(default=True, verbose_name='Ativa no Wifeed',
                                       help_text='Espelho do isActive da API (informativo).')
    ultima_sincronizacao = models.DateTimeField(null=True, blank=True,
                                                verbose_name='Última sincronização do catálogo')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_wifeed_fontes'
        verbose_name = 'Fonte Wifeed'
        verbose_name_plural = '📶 Fontes Wifeed (locais/campanhas)'
        unique_together = [('tipo', 'externo_id')]
        ordering = ['tipo', 'nome']

    def __str__(self):
        return f'{self.get_tipo_display()} · {self.nome or self.externo_id}'


class WifeedConfig(models.Model):
    """Configuração (singleton) da captação Wifeed — intervalo do poller."""
    intervalo_minutos = models.PositiveIntegerField(
        default=15, verbose_name='Intervalo de sincronização (min)',
        help_text='De quantos em quantos minutos o poller busca leads novos.')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_wifeed_config'
        verbose_name = 'Configuração Wifeed'
        verbose_name_plural = '📶 Configuração Wifeed'

    def __str__(self):
        return f'Wifeed a cada {self.intervalo_minutos} min'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
