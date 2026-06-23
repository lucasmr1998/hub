"""
Persistência da engine de automação.

`Fluxo` guarda o grafo (nós + conexões) como JSON — o MESMO formato que o runtime
(`executar_fluxo`) consome e que o editor produz. JSONField em vez de models
normalizados de Nó/Conexão porque o runtime e o editor já falam esse dict; mantém
a impedância zero. (Normalizar depois, se precisar de query por nó.)
"""
from django.conf import settings
from django.db import models

from apps.sistema.mixins import TenantMixin


class Fluxo(TenantMixin):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default='')
    ativo = models.BooleanField(default=True, db_index=True)
    # {inicio, nodes: {handle: {tipo, config, pos, label}}, conexoes: [{de, para, saida}]}
    grafo = models.JSONField(default=dict)
    # Gatilho webhook: token secreto; POST em /automacao/webhook/<token>/ dispara o fluxo.
    webhook_token = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Índice denormalizado do gatilho de evento (preenchido no save a partir do grafo).
    # Permite achar rápido "quais fluxos escutam o evento X" sem varrer JSON em SQL.
    gatilho_evento = models.CharField(max_length=64, blank=True, default='', db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacao_fluxo'
        ordering = ['-atualizado_em']
        verbose_name = 'Fluxo de automação'
        verbose_name_plural = 'Fluxos de automação'

    def _evento_do_grafo(self):
        """Lê o evento do nó-gatilho de evento no grafo (ou '' se não houver)."""
        nodes = (self.grafo or {}).get('nodes') or {}
        for n in nodes.values():
            if n.get('tipo') == 'evento':
                return ((n.get('config') or {}).get('evento') or '').strip()
        return ''

    def save(self, *args, **kwargs):
        # Mantém o índice gatilho_evento sincronizado com o grafo em qualquer save.
        novo = self._evento_do_grafo()
        if novo != self.gatilho_evento:
            self.gatilho_evento = novo
            uf = kwargs.get('update_fields')
            if uf is not None:
                kwargs['update_fields'] = list(set(uf) | {'gatilho_evento'})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class ExecucaoFluxo(TenantMixin):
    """Uma execução de um fluxo. Guarda o estado serializado pra retoma (delay)."""
    STATUS = [
        ('pendente', 'pendente'),  # enfileirada por gatilho; o cron roda (deferido)
        ('rodando', 'rodando'), ('aguardando', 'aguardando'),
        ('completado', 'completado'), ('erro', 'erro'),
    ]
    fluxo = models.ForeignKey(Fluxo, on_delete=models.CASCADE, related_name='execucoes')
    status = models.CharField(max_length=20, choices=STATUS, default='rodando', db_index=True)
    estado = models.JSONField(default=dict)        # Contexto.serializar()
    no_pausado = models.CharField(max_length=200, blank=True, default='')  # handle do nó que pausou
    modo_espera = models.CharField(max_length=20, blank=True, default='')  # '' | 'timer' | 'resposta'
    # Âncora conversacional: o que a execução espera (ex: telefone normalizado).
    chave = models.CharField(max_length=64, blank=True, default='', db_index=True)
    # Âncora de jornada (enrollment): 1 execução ativa por lead por fluxo.
    lead = models.ForeignKey(
        'leads.LeadProspecto', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    agendado_para = models.DateTimeField(null=True, blank=True, db_index=True)
    trace = models.JSONField(default=list)
    erro = models.TextField(blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacao_execucao'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['status', 'agendado_para']),
            models.Index(fields=['status', 'modo_espera', 'chave']),
        ]

    def __str__(self):
        return f'{self.fluxo_id} · {self.status}'


class Agente(TenantMixin):
    """Agente IA gerenciado: prompt + modelo + tools (D3) + conhecimento (D4).

    Definido UMA vez (área /automacao/agentes/) e referenciado pelos fluxos pelo
    nó `ia_agente`. Espelha o padrão da IntegracaoAPI (configura uma vez, usa por id).
    """
    nome = models.CharField(max_length=200)
    integracao_ia = models.ForeignKey(
        'integracoes.IntegracaoAPI', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    # Vazio = usa o modelo default da integração (configuracoes_extras['modelo']).
    modelo = models.CharField(max_length=100, blank=True, default='')
    system_prompt = models.TextField(blank=True, default='')
    # D3: chaves das tools habilitadas (registry em services/ia_tools.py).
    tools = models.JSONField(default=list, blank=True)
    ativo = models.BooleanField(default=True, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacao_agente'
        ordering = ['nome']
        verbose_name = 'Agente IA'
        verbose_name_plural = 'Agentes IA'

    def __str__(self):
        return self.nome
