"""
Espelhos de dados HubSoft pra alimentar relatorios e modulo CS.

Populados via cron periodico chamando endpoints `/todos` paginados:
- FaturaHubsoft     <- /api/v1/integracao/cliente/financeiro (por cliente)
- OrdemServicoHubsoft <- /api/v1/integracao/ordem_servico/todos
- AtendimentoHubsoft  <- /api/v1/integracao/atendimento/todos

Ver `apps/integracoes/services/hubsoft_relatorios.py` pros helpers de sync
e commands em `apps/integracoes/management/commands/sync_base_*_hubsoft.py`.
"""
from django.db import models

from apps.sistema.mixins import TenantMixin


STATUS_FATURA_CHOICES = [
    ('aberta',    'Aberta'),
    ('paga',      'Paga'),
    ('vencida',   'Vencida'),
    ('cancelada', 'Cancelada'),
    ('outro',     'Outro'),
]


class FaturaHubsoft(TenantMixin):
    """
    Espelho de faturas do HubSoft. Endpoint origem: /cliente/financeiro
    (por cliente — nao tem /faturas/todos). Sync itera ClienteHubsoft ativos
    do tenant e UPSERT.
    """
    cliente = models.ForeignKey(
        'integracoes.ClienteHubsoft',
        on_delete=models.CASCADE,
        related_name='faturas',
    )
    id_fatura_hubsoft = models.BigIntegerField(db_index=True, verbose_name='ID Fatura HubSoft')
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    data_emissao = models.DateField(null=True, blank=True, db_index=True)
    data_vencimento = models.DateField(db_index=True)
    data_pagamento = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_FATURA_CHOICES,
        default='aberta', db_index=True,
    )
    forma_pagamento = models.CharField(max_length=80, blank=True, default='')
    linha_digitavel = models.CharField(max_length=120, blank=True, default='')
    descricao = models.CharField(max_length=255, blank=True, default='')
    dados_completos = models.JSONField(default=dict, blank=True)
    sincronizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integracoes_fatura_hubsoft'
        verbose_name = 'Fatura HubSoft'
        verbose_name_plural = 'Faturas HubSoft'
        unique_together = [('tenant', 'id_fatura_hubsoft')]
        indexes = [
            models.Index(fields=['tenant', 'status', 'data_vencimento']),
            models.Index(fields=['tenant', 'data_vencimento']),
            models.Index(fields=['cliente', 'status']),
        ]
        ordering = ['-data_vencimento']

    def __str__(self):
        return f'Fatura #{self.id_fatura_hubsoft} — {self.status} — R$ {self.valor}'


class OrdemServicoHubsoft(TenantMixin):
    """
    Espelho de OS reais do HubSoft (NAO confundir com OrdemServicoTentativa
    que registra tentativas de abertura via Matrix).
    Endpoint origem: /ordem_servico/todos paginado.
    """
    cliente = models.ForeignKey(
        'integracoes.ClienteHubsoft',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordens_servico',
    )
    servico = models.ForeignKey(
        'integracoes.ServicoClienteHubsoft',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordens_servico',
    )
    id_os_hubsoft = models.BigIntegerField(db_index=True, verbose_name='ID OS HubSoft')
    status = models.CharField(max_length=80, db_index=True, default='')
    status_prefixo = models.CharField(max_length=80, blank=True, default='', db_index=True)
    tipo = models.CharField(max_length=120, blank=True, default='')
    tecnico_id = models.IntegerField(null=True, blank=True, db_index=True)
    tecnico_nome = models.CharField(max_length=120, blank=True, default='')
    data_abertura = models.DateTimeField(null=True, blank=True, db_index=True)
    data_agendamento = models.DateTimeField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    descricao = models.TextField(blank=True, default='')
    motivo = models.CharField(max_length=255, blank=True, default='')
    dados_completos = models.JSONField(default=dict, blank=True)
    sincronizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integracoes_ordem_servico_hubsoft'
        verbose_name = 'Ordem de Servico HubSoft'
        verbose_name_plural = 'Ordens de Servico HubSoft'
        unique_together = [('tenant', 'id_os_hubsoft')]
        indexes = [
            models.Index(fields=['tenant', 'status', 'data_abertura']),
            models.Index(fields=['tenant', 'tecnico_id']),
        ]
        ordering = ['-data_abertura']

    def __str__(self):
        return f'OS #{self.id_os_hubsoft} — {self.status}'


class AtendimentoHubsoft(TenantMixin):
    """
    Espelho de atendimentos (chamados) do HubSoft.
    Endpoint origem: /atendimento/todos paginado.
    """
    cliente = models.ForeignKey(
        'integracoes.ClienteHubsoft',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='atendimentos',
    )
    id_atendimento_hubsoft = models.BigIntegerField(db_index=True, verbose_name='ID Atendimento HubSoft')
    status = models.CharField(max_length=80, db_index=True, default='')
    status_prefixo = models.CharField(max_length=80, blank=True, default='', db_index=True)
    tipo = models.CharField(max_length=120, blank=True, default='')
    descricao = models.TextField(blank=True, default='')
    data_abertura = models.DateTimeField(null=True, blank=True, db_index=True)
    data_fechamento = models.DateTimeField(null=True, blank=True)
    dados_completos = models.JSONField(default=dict, blank=True)
    sincronizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integracoes_atendimento_hubsoft'
        verbose_name = 'Atendimento HubSoft'
        verbose_name_plural = 'Atendimentos HubSoft'
        unique_together = [('tenant', 'id_atendimento_hubsoft')]
        indexes = [
            models.Index(fields=['tenant', 'status', 'data_abertura']),
        ]
        ordering = ['-data_abertura']

    def __str__(self):
        return f'Atendimento #{self.id_atendimento_hubsoft} — {self.status}'
