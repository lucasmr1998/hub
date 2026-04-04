from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from apps.sistema.mixins import TenantMixin


# ============================================================================
# REGRA DE AUTOMAÇÃO (principal)
# ============================================================================

class RegraAutomacao(TenantMixin):
    """Regra de automação: pode ser linear (legacy) ou fluxograma visual."""

    EVENTO_CHOICES = [
        ('lead_criado', 'Novo lead criado'),
        ('lead_qualificado', 'Lead qualificado (score mínimo)'),
        ('lead_sem_contato', 'Lead sem contato há X dias'),
        ('oportunidade_movida', 'Oportunidade movida de estágio'),
        ('venda_aprovada', 'Venda aprovada'),
        ('cliente_aniversario', 'Aniversário de cliente'),
        ('indicacao_convertida', 'Indicação convertida'),
        ('tarefa_vencida', 'Tarefa CRM vencida'),
        ('docs_validados', 'Documentos validados'),
        ('lead_entrou_segmento', 'Lead entrou em um segmento'),
        ('disparo_segmento', 'Disparo em massa por segmento'),
        ('mensagem_recebida', 'Mensagem recebida no inbox'),
        ('conversa_aberta', 'Nova conversa aberta no inbox'),
        ('conversa_resolvida', 'Conversa resolvida no inbox'),
    ]

    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    evento = models.CharField(max_length=50, choices=EVENTO_CHOICES)
    ativa = models.BooleanField(default=True, db_index=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='automacoes_criadas')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    # Contadores
    total_execucoes = models.PositiveIntegerField(default=0)
    total_sucesso = models.PositiveIntegerField(default=0)
    total_erro = models.PositiveIntegerField(default=0)

    # Modo fluxo visual (vs legacy linear)
    modo_fluxo = models.BooleanField(default=False, help_text='True = fluxograma visual, False = linear legado')
    fluxo_json = models.JSONField(default=dict, blank=True, help_text='Estado do editor Drawflow para re-import')

    # Segmento como fonte de dados
    segmento = models.ForeignKey(
        'crm.SegmentoCRM', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='automacoes', help_text='Segmento para disparo em massa',
    )

    # Controles de execução
    max_execucoes_por_lead = models.PositiveIntegerField(default=0, help_text='0 = ilimitado')
    cooldown_horas = models.PositiveIntegerField(default=0, help_text='Mínimo de horas entre execuções para o mesmo lead. 0 = sem cooldown')
    periodo_limite_horas = models.PositiveIntegerField(default=24, help_text='Janela de tempo para max_execucoes_por_lead')

    class Meta:
        db_table = 'automacoes_regraautomacao'
        verbose_name = 'Regra de Automação'
        verbose_name_plural = 'Regras de Automação'
        ordering = ['-ativa', '-data_criacao']

    def __str__(self):
        return f'{self.nome} ({self.get_evento_display()})'

    @property
    def taxa_sucesso(self):
        if self.total_execucoes == 0:
            return 100
        return round(self.total_sucesso / self.total_execucoes * 100)


# ============================================================================
# CONDIÇÃO E AÇÃO (modo legacy linear)
# ============================================================================

class CondicaoRegra(TenantMixin):
    """Condição opcional: campo + operador + valor (modo legacy)."""

    OPERADOR_CHOICES = [
        ('igual', 'é igual a'),
        ('diferente', 'é diferente de'),
        ('contem', 'contém'),
        ('maior', 'é maior que'),
        ('menor', 'é menor que'),
        ('maior_igual', 'é maior ou igual a'),
        ('menor_igual', 'é menor ou igual a'),
    ]

    regra = models.ForeignKey(RegraAutomacao, on_delete=models.CASCADE, related_name='condicoes')
    campo = models.CharField(max_length=100, help_text='Ex: lead.origem, lead.score, crm.estagio')
    operador = models.CharField(max_length=20, choices=OPERADOR_CHOICES)
    valor = models.CharField(max_length=255)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'automacoes_condicaoregra'
        verbose_name = 'Condição'
        verbose_name_plural = 'Condições'
        ordering = ['ordem']

    def __str__(self):
        return f'{self.campo} {self.get_operador_display()} {self.valor}'

    def avaliar(self, contexto):
        valor_campo = self._resolver_campo(contexto)
        if valor_campo is None:
            return False
        return self._comparar(valor_campo, self.valor)

    def _resolver_campo(self, contexto):
        partes = self.campo.split('.')
        obj = contexto
        for parte in partes:
            if isinstance(obj, dict):
                obj = obj.get(parte)
            elif hasattr(obj, parte):
                obj = getattr(obj, parte)
            else:
                flat_key = self.campo.replace('.', '_')
                return contexto.get(flat_key)
        return obj

    def _comparar(self, valor_campo, valor_esperado):
        try:
            vc = float(str(valor_campo))
            ve = float(str(valor_esperado))
        except (ValueError, TypeError):
            vc = str(valor_campo).lower()
            ve = str(valor_esperado).lower()

        if self.operador == 'igual':
            return vc == ve
        elif self.operador == 'diferente':
            return vc != ve
        elif self.operador == 'contem':
            return str(ve) in str(vc)
        elif self.operador == 'maior':
            return vc > ve
        elif self.operador == 'menor':
            return vc < ve
        elif self.operador == 'maior_igual':
            return vc >= ve
        elif self.operador == 'menor_igual':
            return vc <= ve
        return False


class AcaoRegra(TenantMixin):
    """Ação a executar (modo legacy linear)."""

    TIPO_CHOICES = [
        ('enviar_whatsapp', 'Enviar WhatsApp'),
        ('enviar_email', 'Enviar E-mail'),
        ('notificacao_sistema', 'Notificação no sistema'),
        ('criar_tarefa', 'Criar tarefa no CRM'),
        ('mover_estagio', 'Mover estágio no pipeline'),
        ('atribuir_responsavel', 'Atribuir responsável'),
        ('dar_pontos', 'Dar pontos no Clube'),
        ('webhook', 'Chamar webhook externo'),
    ]

    regra = models.ForeignKey(RegraAutomacao, on_delete=models.CASCADE, related_name='acoes')
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    configuracao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=0)

    delay_ativo = models.BooleanField(default=False)
    delay_valor = models.PositiveIntegerField(default=0)
    delay_unidade = models.CharField(max_length=10, choices=[
        ('minutos', 'Minutos'), ('horas', 'Horas'), ('dias', 'Dias'),
    ], default='minutos')

    class Meta:
        db_table = 'automacoes_acaoregra'
        verbose_name = 'Ação'
        verbose_name_plural = 'Ações'
        ordering = ['ordem']

    def __str__(self):
        delay = f' (após {self.delay_valor} {self.delay_unidade})' if self.delay_ativo else ''
        return f'{self.get_tipo_display()}{delay}'

    @property
    def delay_timedelta(self):
        if not self.delay_ativo:
            return timedelta(0)
        if self.delay_unidade == 'minutos':
            return timedelta(minutes=self.delay_valor)
        elif self.delay_unidade == 'horas':
            return timedelta(hours=self.delay_valor)
        elif self.delay_unidade == 'dias':
            return timedelta(days=self.delay_valor)
        return timedelta(0)


# ============================================================================
# NODO DO FLUXOGRAMA (modo visual)
# ============================================================================

class NodoFluxo(TenantMixin):
    """Nó do fluxograma visual: gatilho, condição, ação ou delay."""

    TIPO_CHOICES = [
        ('trigger', 'Gatilho'),
        ('condition', 'Condição (If/Else)'),
        ('action', 'Ação'),
        ('delay', 'Atraso'),
    ]

    regra = models.ForeignKey(RegraAutomacao, on_delete=models.CASCADE, related_name='nodos')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    subtipo = models.CharField(max_length=50, blank=True, help_text='Ex: lead_criado, enviar_whatsapp, campo_check')
    configuracao = models.JSONField(default=dict, blank=True, help_text='Config do nó: template, campo/operador/valor, delay, etc.')

    # Posição visual no editor
    pos_x = models.IntegerField(default=0)
    pos_y = models.IntegerField(default=0)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'automacoes_nodofluxo'
        verbose_name = 'Nodo do Fluxo'
        verbose_name_plural = 'Nodos do Fluxo'
        ordering = ['ordem']

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.subtipo or "—"}'


class ConexaoNodo(TenantMixin):
    """Aresta dirigida entre dois nós do fluxograma."""

    TIPO_SAIDA_CHOICES = [
        ('default', 'Padrão'),
        ('true', 'Verdadeiro (Sim)'),
        ('false', 'Falso (Não)'),
    ]

    regra = models.ForeignKey(RegraAutomacao, on_delete=models.CASCADE, related_name='conexoes')
    nodo_origem = models.ForeignKey(NodoFluxo, on_delete=models.CASCADE, related_name='saidas')
    nodo_destino = models.ForeignKey(NodoFluxo, on_delete=models.CASCADE, related_name='entradas')
    tipo_saida = models.CharField(max_length=10, choices=TIPO_SAIDA_CHOICES, default='default')

    class Meta:
        db_table = 'automacoes_conexaonodo'
        verbose_name = 'Conexão'
        verbose_name_plural = 'Conexões'
        unique_together = [['nodo_origem', 'nodo_destino', 'tipo_saida']]

    def __str__(self):
        return f'{self.nodo_origem} → [{self.tipo_saida}] → {self.nodo_destino}'


# ============================================================================
# FILA DE EXECUÇÃO PENDENTE (delays e agendamentos)
# ============================================================================

class ExecucaoPendente(TenantMixin):
    """Fila de ações aguardando execução (delays, agendamentos)."""

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('executado', 'Executado'),
        ('cancelado', 'Cancelado'),
        ('erro', 'Erro'),
    ]

    regra = models.ForeignKey(RegraAutomacao, on_delete=models.CASCADE, related_name='pendentes')
    nodo = models.ForeignKey(NodoFluxo, on_delete=models.SET_NULL, null=True, blank=True, related_name='pendentes')
    acao = models.ForeignKey(AcaoRegra, on_delete=models.SET_NULL, null=True, blank=True, related_name='pendentes')
    lead = models.ForeignKey('leads.LeadProspecto', on_delete=models.CASCADE, null=True, blank=True, related_name='automacoes_pendentes')

    contexto_json = models.JSONField(default=dict, help_text='Contexto serializado para retomar execução')
    data_agendada = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')

    data_criacao = models.DateTimeField(auto_now_add=True)
    data_execucao = models.DateTimeField(null=True, blank=True)
    resultado = models.TextField(blank=True)

    class Meta:
        db_table = 'automacoes_execucaopendente'
        verbose_name = 'Execução Pendente'
        verbose_name_plural = 'Execuções Pendentes'
        ordering = ['data_agendada']
        indexes = [
            models.Index(fields=['status', 'data_agendada']),
            models.Index(fields=['lead', 'status']),
        ]

    def __str__(self):
        return f'{self.regra.nome} — {self.get_status_display()} (agendado: {self.data_agendada:%d/%m %H:%M})'


# ============================================================================
# CONTROLE DE EXECUÇÃO (rate limiting por lead)
# ============================================================================

class ControleExecucao(TenantMixin):
    """Controle de limites de execução por lead por regra."""

    lead = models.ForeignKey('leads.LeadProspecto', on_delete=models.CASCADE, related_name='controles_automacao')
    regra = models.ForeignKey(RegraAutomacao, on_delete=models.CASCADE, related_name='controles')

    total_execucoes_periodo = models.PositiveIntegerField(default=0)
    primeira_execucao_periodo = models.DateTimeField(null=True, blank=True)
    ultima_execucao = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'automacoes_controleexecucao'
        verbose_name = 'Controle de Execução'
        verbose_name_plural = 'Controles de Execução'
        unique_together = [['lead', 'regra']]

    def __str__(self):
        return f'{self.lead} — {self.regra.nome} ({self.total_execucoes_periodo}x)'


# ============================================================================
# LOG DE EXECUÇÃO
# ============================================================================

class LogExecucao(TenantMixin):
    """Registro de cada execução de uma regra (com FK para lead e nodo)."""

    STATUS_CHOICES = [
        ('sucesso', 'Sucesso'),
        ('erro', 'Erro'),
        ('agendado', 'Agendado'),
        ('cancelado', 'Cancelado'),
    ]

    regra = models.ForeignKey(RegraAutomacao, on_delete=models.CASCADE, related_name='logs')
    acao = models.ForeignKey(AcaoRegra, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    nodo = models.ForeignKey(NodoFluxo, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    lead = models.ForeignKey('leads.LeadProspecto', on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_automacao', db_index=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sucesso')
    evento_dados = models.JSONField(default=dict, blank=True)
    resultado = models.TextField(blank=True)
    data_execucao = models.DateTimeField(auto_now_add=True)
    data_agendada = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'automacoes_logexecucao'
        verbose_name = 'Log de Execução'
        verbose_name_plural = 'Logs de Execução'
        ordering = ['-data_execucao']

    def __str__(self):
        return f'{self.regra.nome} — {self.get_status_display()} ({self.data_execucao:%d/%m %H:%M})'
