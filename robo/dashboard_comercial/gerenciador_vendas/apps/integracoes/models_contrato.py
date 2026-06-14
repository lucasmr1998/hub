"""
Painel de Contratos — modelo de tentativas de criar/aceitar contrato HubSoft.

Cada execucao das acoes `_acao_gerar_contrato_hubsoft` ou
`_acao_assinar_contrato_hubsoft` (engine de automacao do CRM) gera uma
ContratoTentativa. Persiste payload, resposta HubSoft, motivo de falha
categorizado e qual etapa do fluxo composto (criar→anexar→aceitar) falhou.
"""
import uuid

from django.conf import settings
from django.db import models

from apps.sistema.mixins import TenantMixin


ACAO_CHOICES = [
    ('gerar',     'Gerar contrato (criar + anexar docs + aceitar)'),
    ('assinar',   'Assinar contrato (aceitar existente)'),
]

ETAPA_CHOICES = [
    ('criar',     'Criar contrato'),
    ('anexar',    'Anexar documentos'),
    ('aceitar',   'Aceitar contrato'),
    ('completo',  'Fluxo completo'),
]

STATUS_TENTATIVA = [
    ('pendente',             'Pendente'),
    ('sucesso',              'Sucesso'),
    ('falha',                'Falha'),
    ('pulado_idempotente',   'Pulado (ja feito)'),
]

CATEGORIAS_FALHA_CONTRATO = [
    ('contrato_ja_existe',     'Contrato ja existe'),
    ('cliente_sem_servico',    'Cliente sem servico'),
    ('modelo_nao_encontrado',  'Modelo nao encontrado'),
    ('documento_rejeitado',    'Documento rejeitado'),
    ('dados_invalidos',        'Dados invalidos'),
    ('token_expirado',         'Token expirado'),
    ('cliente_inexistente',    'Cliente inexistente'),
    ('outro',                  'Outro'),
]

ORIGEM_TENTATIVA = [
    ('automacao_pipeline', 'Automacao do pipeline'),
    ('retry_manual',       'Retry manual'),
]


class ContratoTentativa(TenantMixin):
    """Tentativa de criar/aceitar contrato HubSoft via engine de automacao."""

    # Agrupa retries da mesma oportunidade/lead
    grupo_tentativas_id = models.UUIDField(
        default=uuid.uuid4, editable=False, db_index=True,
        help_text='Agrupa todas as tentativas do mesmo lead/oportunidade',
    )
    tentativa_numero = models.PositiveSmallIntegerField(default=1)

    # Tipo de operacao
    acao = models.CharField(max_length=10, choices=ACAO_CHOICES, db_index=True)
    etapa = models.CharField(
        max_length=12, choices=ETAPA_CHOICES, blank=True,
        help_text='Em qual subtarefa parou (so faz sentido pra acao=gerar)',
    )

    # IDs HubSoft
    id_cliente_servico = models.BigIntegerField(null=True, blank=True, db_index=True)
    id_cliente_servico_contrato = models.BigIntegerField(null=True, blank=True, db_index=True)
    id_modelo_contrato = models.IntegerField(null=True, blank=True)
    id_empresa = models.IntegerField(null=True, blank=True)

    # Relacoes
    lead = models.ForeignKey(
        'leads.LeadProspecto', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contrato_tentativas',
    )
    cliente_hubsoft = models.ForeignKey(
        'integracoes.ClienteHubsoft', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contrato_tentativas',
    )
    servico = models.ForeignKey(
        'integracoes.ServicoClienteHubsoft', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contrato_tentativas',
    )
    oportunidade = models.ForeignKey(
        'crm.OportunidadeVenda', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contrato_tentativas',
    )
    integracao = models.ForeignKey(
        'integracoes.IntegracaoAPI', on_delete=models.PROTECT,
        related_name='contrato_tentativas',
    )
    regra_automacao = models.ForeignKey(
        'crm.RegraPipelineEstagio', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contrato_tentativas',
        help_text='Regra que disparou (quando origem=automacao_pipeline)',
    )

    # Estado
    status = models.CharField(
        max_length=20, choices=STATUS_TENTATIVA, default='pendente', db_index=True,
    )
    motivo_falha_categoria = models.CharField(
        max_length=25, choices=CATEGORIAS_FALHA_CONTRATO, blank=True, db_index=True,
    )
    motivo_falha_mensagem = models.TextField(blank=True)

    # Payload + resposta brutos
    payload_enviado = models.JSONField(default=dict, blank=True)
    resposta_hubsoft = models.JSONField(default=dict, blank=True)
    anexos_enviados = models.JSONField(
        default=list, blank=True,
        help_text='Lista de {nome, tamanho_bytes, mime} quando etapa=anexar',
    )

    # Auditoria
    duracao_ms = models.PositiveIntegerField(default=0)
    origem = models.CharField(max_length=20, choices=ORIGEM_TENTATIVA, default='automacao_pipeline')
    usuario_retry = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contrato_retries',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'integracoes_contrato_tentativa'
        verbose_name = 'Tentativa de Contrato'
        verbose_name_plural = 'Tentativas de Contrato'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', '-criado_em'], name='contrato_tent_tenant_data_idx'),
            models.Index(fields=['tenant', 'status', '-criado_em'], name='contrato_tent_status_idx'),
            models.Index(fields=['tenant', 'acao', '-criado_em'], name='contrato_tent_acao_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['grupo_tentativas_id', 'tentativa_numero'],
                name='uniq_contrato_tent_por_grupo',
            ),
        ]

    def __str__(self):
        lead_id = self.lead_id or '?'
        return f'Contrato({self.acao}) lead={lead_id} tentativa {self.tentativa_numero} ({self.status})'

    @property
    def foi_sucesso(self):
        return self.status == 'sucesso'

    @property
    def foi_falha(self):
        return self.status == 'falha'
