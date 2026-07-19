"""Modelos de auditoria da automação HubSoft.

Toda tentativa de executar um processo (conversão, novo serviço, upgrade) — seja
via webdriver ou via API interna — gera um `ExecucaoHubsoft`. Isso dá histórico,
permite comparar latência webdriver vs API e diagnosticar falhas. `CapturaAPI`
guarda os endpoints/payloads capturados de um fluxo (para validar a migração
webdriver → API).
"""
from django.db import models


class ExecucaoHubsoft(models.Model):
    PROCESSO_CHOICES = [
        ('conversao',    'Conversão prospecto → cliente'),
        ('novo_servico', 'Novo serviço'),
        ('upgrade',      'Upgrade de plano'),
    ]
    EXECUTOR_CHOICES = [
        ('api_interna', 'API interna'),
        ('webdriver',   'Webdriver'),
    ]
    STATUS_CHOICES = [
        ('sucesso', 'Sucesso'),
        ('falha',   'Falha'),
        ('dry_run', 'Dry-run (não salvou)'),
    ]

    processo = models.CharField(max_length=20, choices=PROCESSO_CHOICES, db_index=True)
    registro_id = models.IntegerField(
        help_text='ID do NewService / UpgradePlano / prospecto processado', db_index=True)
    executor = models.CharField(max_length=20, choices=EXECUTOR_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, db_index=True)
    dry_run = models.BooleanField(default=True)
    tentativa_fallback = models.BooleanField(
        default=False, help_text='True se esta execução foi o fallback após o primário falhar')

    etapa = models.CharField(max_length=80, blank=True, default='')
    erro = models.TextField(blank=True, default='')
    metadados = models.JSONField(default=dict, blank=True,
                                 help_text='ids criados no HubSoft, etc.')
    duracao_ms = models.IntegerField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'posvenda_execucao_hubsoft'
        verbose_name = 'Execução HubSoft'
        verbose_name_plural = 'Execuções HubSoft'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['processo', 'registro_id']),
            models.Index(fields=['status', 'criado_em']),
        ]

    def __str__(self):
        return f'{self.processo} #{self.registro_id} [{self.executor}] → {self.status}'


class CapturaAPI(models.Model):
    """Endpoints/payloads capturados (CDP) de um fluxo do HubSoft — referência para
    montar/validar os payloads da API interna."""
    processo = models.CharField(max_length=20, db_index=True)
    registro_id = models.IntegerField(null=True, blank=True)
    metodo = models.CharField(max_length=8)
    endpoint = models.CharField(max_length=255)
    payload = models.JSONField(default=dict, blank=True)
    resposta = models.JSONField(default=dict, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'posvenda_captura_api'
        verbose_name = 'Captura de API'
        verbose_name_plural = 'Capturas de API'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.metodo} {self.endpoint} ({self.status_code})'
