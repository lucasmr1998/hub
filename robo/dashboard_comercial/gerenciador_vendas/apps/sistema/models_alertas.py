"""Models de Alertas do sistema. Tarefa Workspace #152.

Alerta = evento operacional que merece ser visto pelo admin.
Envio via uazapi pro telefone configurado (hoje 53981521653 hardcoded como
teste).

Tipos: cron_falhou, webhook_5xx, hubsoft_erro, catalogo_mudou,
       lead_travado, uazapi_caiu, bot_falhou, erro_python_critico.

Dedup: mesma chave dentro de 5min nao dispara WhatsApp duas vezes. Mas
*sempre* cria o registro em DB pra historico no admin.
"""
from django.db import models
from django.utils import timezone


class AlertaSistema(models.Model):
    """Registro de alerta operacional. NAO usa TenantMixin: alertas sao
    globais (admin Aurora-HQ), nao filtrados por tenant. O campo tenant
    abaixo eh OPCIONAL e serve apenas pra contextualizar qual cliente
    disparou o alerta (ex: "HubSoft Nuvyon falhou")."""

    TIPO_CHOICES = [
        ('cron_falhou', 'CronJob falhou'),
        ('cron_lag', 'CronJob nao rodou no schedule'),
        ('webhook_5xx', 'Webhook N8N retornou 5xx'),
        ('hubsoft_erro', 'HubSoft API com erros consecutivos'),
        ('catalogo_mudou', 'Catalogo HubSoft mudou (vendedor/origem sumiu)'),
        ('lead_travado', 'Lead em status erro ha > 1h'),
        ('uazapi_caiu', 'uazapi sem token / instancia caiu'),
        ('bot_falhou', 'Bot Selenium falhou'),
        ('erro_python', 'Erro Python critico'),
        ('outro', 'Outro'),
    ]

    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, db_index=True)
    titulo = models.CharField(max_length=200, verbose_name='Titulo (vai no WhatsApp)')
    mensagem = models.TextField(verbose_name='Mensagem detalhada')
    dados_extras = models.JSONField(default=dict, blank=True,
                                    verbose_name='Dados estruturados (entidade_id, etc)')
    dedup_key = models.CharField(
        max_length=200, db_index=True,
        verbose_name='Chave de deduplicacao (5min)',
        help_text='Mesma chave dentro da janela nao reenvia WhatsApp',
    )
    tenant = models.ForeignKey(
        'sistema.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alertas_disparados',
        verbose_name='Tenant que disparou (contexto)',
    )

    criado_em = models.DateTimeField(default=timezone.now, db_index=True)
    enviado_em = models.DateTimeField(null=True, blank=True,
                                      verbose_name='Quando saiu por WhatsApp')
    suprimido = models.BooleanField(
        default=False,
        verbose_name='Suprimido por dedup',
        help_text='Marcado True quando uma chave dedup repete dentro da janela',
    )
    erro_envio = models.TextField(blank=True, default='',
                                  verbose_name='Erro ao enviar (se falhou)')

    class Meta:
        db_table = 'sistema_alerta'
        verbose_name = 'Alerta do sistema'
        verbose_name_plural = 'Alertas do sistema'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['dedup_key', 'criado_em']),
            models.Index(fields=['tipo', 'criado_em']),
        ]

    def __str__(self):
        return f'[{self.tipo}] {self.titulo[:60]}'


class AlertaConfig(models.Model):
    """Configuracao global de alertas — singleton.

    Permite mudar o telefone destino sem deploy (admin edita).
    """

    telefone_destino = models.CharField(
        max_length=20, default='53981521653',
        verbose_name='Telefone WhatsApp destino',
        help_text='Numero do operador que recebe alertas (formato 55XX...)',
    )
    janela_dedup_minutos = models.PositiveIntegerField(
        default=5,
        verbose_name='Janela dedup (minutos)',
        help_text='Mesma chave nao reenvia WhatsApp dentro desta janela',
    )
    enviar_whatsapp = models.BooleanField(
        default=True,
        verbose_name='Enviar via WhatsApp',
        help_text='Se desligado, alertas sao apenas logados no admin',
    )
    tipos_ativos = models.JSONField(
        default=list, blank=True,
        verbose_name='Tipos de alerta ativos',
        help_text='Lista de tipos que disparam WhatsApp. Vazio = todos.',
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sistema_alerta_config'
        verbose_name = 'Configuracao de alertas'
        verbose_name_plural = 'Configuracao de alertas'

    def __str__(self):
        return f'Config alertas (tel={self.telefone_destino})'

    @classmethod
    def get_solo(cls):
        """Retorna a config singleton — cria com defaults se nao existe."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
