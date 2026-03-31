from django.db import models
from apps.sistema.mixins import TenantMixin


class ScoreCliente(TenantMixin):
    """Health Score do cliente para previsão de churn."""
    cliente = models.ForeignKey(
        'integracoes.ClienteHubsoft',
        on_delete=models.CASCADE,
    )
    score = models.IntegerField(
        default=50, verbose_name="Health Score (0-100)"
    )
    fatores = models.JSONField(
        default=dict, blank=True, verbose_name="Fatores do Score"
    )
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Score de Cliente"
        verbose_name_plural = "Scores de Clientes"

    def __str__(self):
        return f"Score {self.score} - Cliente #{self.cliente_id}"


class AlertaChurn(TenantMixin):
    """Alerta de risco de cancelamento identificado pelo sistema."""
    cliente = models.ForeignKey(
        'integracoes.ClienteHubsoft',
        on_delete=models.CASCADE,
    )
    tipo = models.CharField(
        max_length=30,
        choices=[
            ('inadimplencia', 'Inadimplência'),
            ('sem_uso', 'Sem uso'),
            ('reclamacao', 'Reclamação'),
            ('contrato_expirando', 'Contrato expirando'),
        ],
    )
    severidade = models.CharField(
        max_length=10,
        choices=[
            ('baixa', 'Baixa'),
            ('media', 'Média'),
            ('alta', 'Alta'),
            ('critica', 'Crítica'),
        ],
        default='media',
    )
    descricao = models.TextField(blank=True)
    resolvido = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_resolucao = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Alerta de Churn"
        verbose_name_plural = "Alertas de Churn"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Alerta {self.tipo} ({self.severidade}) - Cliente #{self.cliente_id}"


class AcaoRetencao(TenantMixin):
    """Ação tomada em resposta a um alerta de churn."""
    alerta = models.ForeignKey(
        AlertaChurn,
        on_delete=models.CASCADE,
        related_name='acoes',
    )
    tipo_acao = models.CharField(
        max_length=30,
        choices=[
            ('contato_whatsapp', 'Contato WhatsApp'),
            ('oferta_desconto', 'Oferta de desconto'),
            ('upgrade_plano', 'Upgrade de plano'),
            ('visita_tecnica', 'Visita técnica'),
        ],
    )
    descricao = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    executada = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_execucao = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ação de Retenção"
        verbose_name_plural = "Ações de Retenção"

    def __str__(self):
        status = "executada" if self.executada else "pendente"
        return f"{self.tipo_acao} ({status})"
