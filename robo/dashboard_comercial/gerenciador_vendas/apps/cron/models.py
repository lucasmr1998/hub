"""Models do dispatcher de cron. Cross-tenant — sem TenantMixin."""
from django.db import models


class CronJob(models.Model):
    """Declara um job periodico do Hubtrix.

    O dispatcher roda a cada 1min e dispara este job sempre que a
    expressao `schedule` (cron classico de 5 campos: min hour dom mon dow)
    bater com o minuto atual.
    """
    STATUS_CHOICES = [
        ('nunca', 'Nunca executou'),
        ('running', 'Rodando'),
        ('success', 'Sucesso'),
        ('erro', 'Erro'),
        ('timeout', 'Timeout'),
    ]

    nome = models.CharField(max_length=120, unique=True, verbose_name='Nome')
    descricao = models.TextField(blank=True, default='', verbose_name='Descricao')
    command = models.CharField(
        max_length=100, verbose_name='Management command',
        help_text='Nome do command sem args. Ex: encerrar_inativos'
    )
    args = models.CharField(
        max_length=500, blank=True, default='', verbose_name='Args',
        help_text='Argumentos do command, separados por espaco. Ex: --tenant tr-carrion --horas 48'
    )
    schedule = models.CharField(
        max_length=80, verbose_name='Schedule (cron expression)',
        help_text='5 campos: minuto hora dia-do-mes mes dia-da-semana. Ex: */15 * * * *'
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    timeout_segundos = models.PositiveIntegerField(
        default=600, verbose_name='Timeout (s)',
        help_text='Mata o processo se passar disso. Default 10min.'
    )
    last_run_at = models.DateTimeField(null=True, blank=True, verbose_name='Ultima execucao')
    last_status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='nunca',
        verbose_name='Ultimo status'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cron_jobs'
        verbose_name = 'Cron Job'
        verbose_name_plural = 'Cron Jobs'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.schedule})'


class ExecucaoCron(models.Model):
    """Log de uma execucao de CronJob. Mantem stdout/stderr pra debug."""
    STATUS_CHOICES = [
        ('running', 'Rodando'),
        ('success', 'Sucesso'),
        ('erro', 'Erro'),
        ('timeout', 'Timeout'),
    ]

    cron_job = models.ForeignKey(
        CronJob, on_delete=models.CASCADE, related_name='execucoes',
        verbose_name='Cron Job'
    )
    inicio = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Inicio')
    fim = models.DateTimeField(null=True, blank=True, verbose_name='Fim')
    duracao_segundos = models.FloatField(null=True, blank=True, verbose_name='Duracao (s)')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='running')
    return_code = models.IntegerField(null=True, blank=True, verbose_name='Return code')
    stdout = models.TextField(blank=True, default='')
    stderr = models.TextField(blank=True, default='')
    disparado_por = models.CharField(
        max_length=80, default='dispatcher',
        verbose_name='Disparado por',
        help_text='"dispatcher" (automatico) ou "manual:<username>"'
    )

    class Meta:
        db_table = 'cron_execucoes'
        verbose_name = 'Execucao de Cron'
        verbose_name_plural = 'Execucoes de Cron'
        ordering = ['-inicio']
        indexes = [
            models.Index(fields=['cron_job', '-inicio']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.cron_job.nome} @ {self.inicio:%Y-%m-%d %H:%M} [{self.status}]'
