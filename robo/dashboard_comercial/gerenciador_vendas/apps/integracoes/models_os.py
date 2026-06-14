"""
Painel de Ordens de Servico — modelo de tentativas de abertura via Matrix.

Cada chamada a `POST /api/public/n8n/matrix/abrir-os/` gera 1 OrdemServicoTentativa,
persistindo payload, resposta do HubSoft e motivo de falha categorizado.
"""
import uuid

from django.conf import settings
from django.db import models

from apps.sistema.mixins import TenantMixin


CATEGORIAS_FALHA = [
    ('tecnico_ocupado',   'Tecnico ocupado'),
    ('slot_indisponivel', 'Horario indisponivel'),
    ('data_invalida',     'Data invalida'),
    ('id_invalido',       'ID de atendimento invalido'),
    ('outro',             'Outro'),
]

STATUS_TENTATIVA = [
    ('pendente', 'Pendente'),
    ('sucesso',  'Sucesso'),
    ('falha',    'Falha'),
]

ORIGEM_TENTATIVA = [
    ('matrix',       'Matrix (automatico)'),
    ('retry_manual', 'Retry manual'),
]


class OrdemServicoTentativa(TenantMixin):
    """Tentativa de abertura de OS via HubSoft. Granularidade = 1 chamada."""

    # Agrupa retries do mesmo atendimento HubSoft
    grupo_tentativas_id = models.UUIDField(
        default=uuid.uuid4, editable=False, db_index=True,
        help_text='Agrupa todas as tentativas do mesmo id_atendimento_hubsoft',
    )
    tentativa_numero = models.PositiveSmallIntegerField(default=1)

    # Identificadores HubSoft
    id_atendimento_hubsoft = models.BigIntegerField(null=True, blank=True, db_index=True)
    id_ordem_servico_hubsoft = models.BigIntegerField(null=True, blank=True, db_index=True)

    # Relacoes (todas nullable - tentativa pode preceder cadastro completo)
    lead = models.ForeignKey(
        'leads.LeadProspecto', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='os_tentativas',
    )
    cliente_hubsoft = models.ForeignKey(
        'integracoes.ClienteHubsoft', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='os_tentativas',
    )
    servico = models.ForeignKey(
        'integracoes.ServicoClienteHubsoft', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='os_tentativas',
    )
    integracao = models.ForeignKey(
        'integracoes.IntegracaoAPI', on_delete=models.PROTECT,
        related_name='os_tentativas',
    )

    # Estado
    status = models.CharField(
        max_length=10, choices=STATUS_TENTATIVA, default='pendente', db_index=True,
    )
    motivo_falha_categoria = models.CharField(
        max_length=20, choices=CATEGORIAS_FALHA, blank=True, db_index=True,
    )
    motivo_falha_mensagem = models.TextField(blank=True)

    # Payload + resposta brutos
    payload_enviado = models.JSONField(default=dict, blank=True)
    resposta_hubsoft = models.JSONField(default=dict, blank=True)

    # Slot solicitado
    data_inicio_programado = models.DateField(null=True, blank=True, db_index=True)
    hora_inicio_programado = models.TimeField(null=True, blank=True)
    data_termino_programado = models.DateField(null=True, blank=True)
    hora_termino_programado = models.TimeField(null=True, blank=True)
    id_tecnico = models.IntegerField(null=True, blank=True, db_index=True)
    tecnico_nome = models.CharField(max_length=200, blank=True)
    cidade = models.CharField(max_length=120, blank=True, db_index=True)

    # Auditoria
    duracao_ms = models.PositiveIntegerField(default=0)
    origem = models.CharField(max_length=15, choices=ORIGEM_TENTATIVA, default='matrix')
    usuario_retry = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='os_retries',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'integracoes_ordem_servico_tentativa'
        verbose_name = 'Tentativa de OS'
        verbose_name_plural = 'Tentativas de OS'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', '-criado_em'], name='os_tent_tenant_data_idx'),
            models.Index(fields=['tenant', 'status', '-criado_em'], name='os_tent_tenant_status_idx'),
            models.Index(fields=['tenant', 'id_atendimento_hubsoft'], name='os_tent_atend_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['grupo_tentativas_id', 'tentativa_numero'],
                name='uniq_tentativa_por_grupo',
            ),
        ]

    def __str__(self):
        return f'OS#{self.id_atendimento_hubsoft or "?"} tentativa {self.tentativa_numero} ({self.status})'

    @property
    def foi_sucesso(self):
        return self.status == 'sucesso'

    @property
    def foi_falha(self):
        return self.status == 'falha'
