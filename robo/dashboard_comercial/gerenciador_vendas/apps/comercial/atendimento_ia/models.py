"""
Persistencia do bot conversacional (Fase 2).

O checklist configuravel (apps.automacao.Checklist / ItemChecklist, Fase 1)
diz O QUE perguntar. Este app diz ONDE cada conversa do bot Matrix parou
nesse roteiro (`SessaoAtendimentoBot`) e guarda a telemetria de cada
tentativa de resposta, valida ou nao (`TentativaResposta`).

A sessao ancora em LEAD (nao no par generico entidade_tipo/entidade_id do
checklist): e assim que o Matrix identifica a conversa, pelo telefone. O
contrato desta fase (endpoints /ia/*) cobre o checklist de contexto
bot_vendas, que mira lead.
"""
from django.db import models

from apps.sistema.mixins import TenantMixin


class SessaoAtendimentoBot(TenantMixin):
    """Maquina de estados de UMA conversa do bot Matrix."""

    STATUS_CHOICES = [
        ('em_andamento', 'Em andamento'),
        ('aguardando_resposta', 'Aguardando resposta do cliente'),
        ('aguardando_recontato', 'Aguardando recontato (timeout do cliente)'),
        ('transbordado', 'Transbordado para atendimento humano'),
        ('finalizado', 'Checklist completo'),
    ]

    lead = models.ForeignKey(
        'leads.LeadProspecto', null=True, blank=True,
        on_delete=models.CASCADE, related_name='sessoes_bot',
    )
    # Chave alternativa: identifica a conversa antes de existir lead_id (a
    # primeira chamada de /ia/proximo-passo pode chegar sem lead ainda).
    cellphone = models.CharField(max_length=20, db_index=True)
    checklist = models.ForeignKey(
        'automacao.Checklist', on_delete=models.PROTECT, related_name='+',
    )
    item_atual = models.ForeignKey(
        'automacao.ItemChecklist', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='em_andamento')
    motivo_transbordo = models.CharField(max_length=60, blank=True, default='')
    tentativas_item = models.PositiveSmallIntegerField(default=0)
    tentativas_recontato = models.PositiveSmallIntegerField(default=0)
    is_cliente_ativo = models.BooleanField(default=False)
    ultima_interacao_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'atendimento_ia_sessao'
        indexes = [
            models.Index(fields=['tenant', 'lead']),
            models.Index(fields=['tenant', 'cellphone', 'status']),
        ]
        ordering = ['-ultima_interacao_em']
        verbose_name = 'Sessao do bot conversacional'
        verbose_name_plural = 'Sessoes do bot conversacional'

    def __str__(self):
        return f'{self.cellphone} · {self.status}'


class TentativaResposta(TenantMixin):
    """TODA tentativa de resposta a um item do checklist, valida ou nao.

    Telemetria de friccao: mostra onde o bot mais erra, para calibrar
    pergunta, validacao e mensagem de erro por item.

    `fonte_validacao` esperado: opcoes, tipo, regex, ia, fallback ou vazio
    (item sem validacao configurada).
    """

    sessao = models.ForeignKey(SessaoAtendimentoBot, on_delete=models.CASCADE, related_name='tentativas')
    item = models.ForeignKey('automacao.ItemChecklist', on_delete=models.CASCADE, related_name='+')
    numero = models.PositiveSmallIntegerField(default=1)
    resposta = models.TextField(blank=True, default='')
    # None = IA indisponivel/timeout: aceito com ressalva (fonte='fallback').
    valida = models.BooleanField(null=True)
    fonte_validacao = models.CharField(max_length=20, blank=True, default='')
    motivo_erro = models.CharField(max_length=200, blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'atendimento_ia_tentativa'
        ordering = ['-criado_em']
        verbose_name = 'Tentativa de resposta do bot'
        verbose_name_plural = 'Tentativas de resposta do bot'

    def __str__(self):
        return f'{self.sessao_id} · item {self.item_id} · tentativa {self.numero}'
