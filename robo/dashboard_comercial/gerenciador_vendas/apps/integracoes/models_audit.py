"""Audit log de chamadas a endpoints publicos N8N.

Sem TenantMixin — eh log cross-tenant (Aurora-HQ owns it).
Retencao curta: rotina de cleanup mantem ultimas 7 dias (ver
management/commands/limpar_logs_webhook_n8n.py — a criar quando virar carga).
"""
from django.db import models


class LogWebhookN8N(models.Model):
    endpoint = models.CharField(max_length=255, db_index=True)
    metodo = models.CharField(max_length=10)
    status_code = models.PositiveIntegerField(db_index=True)
    duracao_ms = models.PositiveIntegerField()
    ip_origem = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    body_preview = models.TextField(blank=True, help_text='Primeiros 2000 chars do body')
    criado_em = models.DateTimeField(db_index=True)

    class Meta:
        db_table = 'integracoes_log_webhook_n8n'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['endpoint', 'status_code']),
            models.Index(fields=['-criado_em', 'status_code']),
        ]

    def __str__(self):
        return f'{self.criado_em:%d/%m %H:%M:%S} {self.metodo} {self.endpoint} → {self.status_code}'
